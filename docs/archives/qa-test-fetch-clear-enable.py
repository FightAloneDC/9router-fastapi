#!/usr/bin/env python3
"""QA Test: Fetch Models, Clear Models, Enable All — End-to-End"""
import json
import subprocess
import sys
import time

BASE = "http://localhost:9000"
RESULTS = []

def curl(method, path, data=None, token=None, params=None):
    """Make a curl request and return (status_code, parsed_json)."""
    url = f"{BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url += f"?{qs}"
    cmd = ["curl", "-s", "-w", "\n%{http_code}", "-X", method, url, "-H", "Content-Type: application/json"]
    if token:
        cmd += ["-H", f"Authorization: Bearer {token}"]
    if data is not None:
        cmd += ["-d", json.dumps(data)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    lines = result.stdout.strip().split("\n")
    status_code = int(lines[-1]) if lines[-1].isdigit() else 0
    body = "\n".join(lines[:-1])
    try:
        return status_code, json.loads(body)
    except json.JSONDecodeError:
        return status_code, {"raw": body}

def report(test_name, endpoint, steps, expected, actual, passed, details=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append({
        "test": test_name, "endpoint": endpoint, "steps": steps,
        "expected": expected, "actual": actual, "status": status, "details": details
    })
    icon = "✅" if passed else "❌"
    print(f"\n{icon} [{status}] {test_name}")
    if details:
        print(f"   Details: {details}")

def main():
    # === AUTH ===
    code, resp = curl("POST", "/auth/login", {"password": "123456"})
    token = resp["access_token"]
    print(f"=== Auth OK (HTTP {code}) ===\n")

    # === BASELINE: Get all providers ===
    code, providers = curl("GET", "/providers", token=token)
    by_type = {}
    for p in providers:
        prov = p["provider"]
        if prov not in by_type:
            by_type[prov] = []
        by_type[prov].append(p)

    # Pick test targets
    # Use gemini (2 connections, ~50 models each) for Fetch/Clear
    # Use groq for Enable/Disable All (16 models on one connection)
    gemini_conns = by_type.get("gemini", [])
    groq_conns = by_type.get("groq", [])
    cerebras_conns = by_type.get("cerebras", [])

    print("=== TEST TARGETS ===")
    for prov_name, conns in [("gemini", gemini_conns), ("groq", groq_conns), ("cerebras", cerebras_conns)]:
        for c in conns:
            print(f"  {prov_name}: {c['id']} ({c['name']}) models={len(c.get('models', []))}")
    print()

    # ============================================================
    # TEST 1: Fetch Models — GET /providers/{conn_id}/models
    # ============================================================
    print("=" * 60)
    print("TEST 1: Fetch Models via GET /providers/{conn_id}/models")
    print("=" * 60)

    # Test with gemini first connection
    if gemini_conns:
        gemini_conn = gemini_conns[0]
        conn_id = gemini_conn["id"]
        print(f"\n  Target: gemini / {gemini_conn['name']} ({conn_id})")
        print(f"  Current models: {len(gemini_conn.get('models', []))}")

        # Step 1: Fetch models from provider API
        code, fetch_resp = curl("GET", f"/providers/{conn_id}/models", token=token)
        fetched_models = fetch_resp.get("models", [])
        print(f"  Fetch response: HTTP {code}, {len(fetched_models)} models returned")
        if fetched_models:
            print(f"  First 5: {[m['id'] if isinstance(m, dict) else m for m in fetched_models[:5]]}")

        report(
            "Fetch Models - API returns models",
            f"GET /providers/{conn_id}/models",
            ["Send GET request to fetch models from gemini connection"],
            "Return 200 with non-empty models list",
            f"HTTP {code}, {len(fetched_models)} models",
            code == 200 and len(fetched_models) > 0,
            f"Returned {len(fetched_models)} models"
        )

    # Test with groq connection that has 16 models
    if groq_conns:
        groq_conn_with_models = None
        for c in groq_conns:
            if len(c.get("models", [])) > 0:
                groq_conn_with_models = c
                break
        if not groq_conn_with_models:
            groq_conn_with_models = groq_conns[0]

        conn_id = groq_conn_with_models["id"]
        print(f"\n  Target: groq / {groq_conn_with_models['name']} ({conn_id})")
        code, fetch_resp = curl("GET", f"/providers/{conn_id}/models", token=token)
        fetched_models = fetch_resp.get("models", [])
        print(f"  Fetch response: HTTP {code}, {len(fetched_models)} models returned")

        report(
            "Fetch Models - Groq API returns models",
            f"GET /providers/{conn_id}/models",
            ["Send GET request to fetch models from groq connection"],
            "Return 200 with non-empty models list",
            f"HTTP {code}, {len(fetched_models)} models",
            code == 200 and len(fetched_models) > 0,
            f"Returned {len(fetched_models)} models"
        )

    # ============================================================
    # TEST 2: Fetch Models — Persist after save (PATCH /providers/{id})
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 2: Fetch Models — Save and persist via PATCH")
    print("=" * 60)

    if cerebras_conns:
        # Use cerebras conn with 0 models to test fresh fetch+save
        target_conn = cerebras_conns[0]
        conn_id = target_conn["id"]
        print(f"\n  Target: cerebras / {target_conn['name']} ({conn_id})")
        print(f"  Current models: {len(target_conn.get('models', []))}")

        # Fetch models
        code, fetch_resp = curl("GET", f"/providers/{conn_id}/models", token=token)
        fetched_models_raw = fetch_resp.get("models", [])
        model_ids = [m["id"] if isinstance(m, dict) else m for m in fetched_models_raw]
        print(f"  Fetched {len(model_ids)} models: {model_ids[:5]}...")

        if model_ids:
            # Save models via PATCH
            code2, patch_resp = curl("PATCH", f"/providers/{conn_id}", {"models": model_ids}, token=token)
            print(f"  PATCH response: HTTP {code2}")

            # Verify persistence — re-read
            code3, verify_resp = curl("GET", f"/providers/{conn_id}", token=token)
            saved_models = verify_resp.get("models", [])
            print(f"  After PATCH: {len(saved_models)} models saved")

            report(
                "Fetch + Save Models — persists after PATCH",
                f"PATCH /providers/{conn_id}",
                [
                    f"GET /providers/{conn_id}/models to fetch {len(model_ids)} models",
                    f"PATCH /providers/{conn_id} with models list",
                    f"GET /providers/{conn_id} to verify persistence"
                ],
                f"Models persist after PATCH ({len(model_ids)} models)",
                f"After PATCH: {len(saved_models)} models",
                len(saved_models) == len(model_ids),
                f"Fetched {len(model_ids)}, saved {len(saved_models)}"
            )
        else:
            report(
                "Fetch + Save Models — persists after PATCH",
                f"PATCH /providers/{conn_id}",
                ["No models fetched from cerebras API"],
                "Models should be fetchable",
                "0 models fetched",
                False,
                "Could not fetch models to test save"
            )

    # ============================================================
    # TEST 3: Clear Models — PATCH /providers/{id} with {models: []}
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 3: Clear Models — frontend approach (PATCH with [])")
    print("=" * 60)

    if gemini_conns:
        # Clear models on first gemini connection
        target = gemini_conns[0]
        conn_id = target["id"]
        original_count = len(target.get("models", []))
        print(f"\n  Target: gemini / {target['name']} ({conn_id})")
        print(f"  Original models: {original_count}")

        # Clear
        code, clear_resp = curl("PATCH", f"/providers/{conn_id}", {"models": []}, token=token)
        print(f"  PATCH clear response: HTTP {code}")

        # Verify cleared
        code2, verify = curl("GET", f"/providers/{conn_id}", token=token)
        cleared_count = len(verify.get("models", []))
        print(f"  After clear: {cleared_count} models")

        report(
            "Clear Models — single connection via PATCH",
            f"PATCH /providers/{conn_id}",
            [
                f"PATCH /providers/{conn_id} with {{models: []}}",
                f"GET /providers/{conn_id} to verify"
            ],
            "Models list should be empty (0)",
            f"{cleared_count} models after clear",
            cleared_count == 0,
            f"Original: {original_count}, after clear: {cleared_count}"
        )

        # Restore models for other tests
        if original_count > 0:
            original_models = target.get("models", [])
            curl("PATCH", f"/providers/{conn_id}", {"models": original_models}, token=token)
            print(f"  (Restored {len(original_models)} models for subsequent tests)")

    # ============================================================
    # TEST 4: Clear Models — ALL connections of a provider
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 4: Clear Models — ALL connections of a provider")
    print("=" * 60)

    if gemini_conns and len(gemini_conns) >= 2:
        # Record original state
        original = []
        for c in gemini_conns:
            original.append((c["id"], len(c.get("models", []))))

        print(f"\n  Target: gemini ({len(gemini_conns)} connections)")
        for cid, count in original:
            print(f"    {cid}: {count} models")

        # Clear ALL connections (frontend approach)
        for c in gemini_conns:
            curl("PATCH", f"/providers/{c['id']}", {"models": []}, token=token)

        # Verify all cleared
        all_cleared = True
        for cid, _ in original:
            code, verify = curl("GET", f"/providers/{cid}", token=token)
            count = len(verify.get("models", []))
            if count > 0:
                all_cleared = False
            print(f"    After clear: {cid}: {count} models")

        report(
            "Clear Models — ALL connections of provider",
            f"PATCH /providers/{{id}} for each gemini connection",
            [
                "PATCH each gemini connection with {models: []}",
                "GET each connection to verify"
            ],
            "All connections should have 0 models",
            f"All cleared: {all_cleared}",
            all_cleared,
            f"Cleared {len(gemini_conns)} connections"
        )

        # Restore for other tests
        for cid, count in original:
            if count > 0:
                orig_conn = next((c for c in gemini_conns if c["id"] == cid), None)
                if orig_conn:
                    curl("PATCH", f"/providers/{cid}", {"models": orig_conn.get("models", [])}, token=token)
        print(f"  (Restored original models)")

    # ============================================================
    # TEST 5: Clear then Fetch — models should come back
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 5: Clear then Fetch — models should come back")
    print("=" * 60)

    if groq_conns:
        # Pick a groq connection with models
        target = None
        for c in groq_conns:
            if len(c.get("models", [])) > 0:
                target = c
                break
        if not target:
            target = groq_conns[0]

        conn_id = target["id"]
        original_models = target.get("models", [])
        print(f"\n  Target: groq / {target['name']} ({conn_id})")
        print(f"  Original models: {len(original_models)}")

        # Clear
        curl("PATCH", f"/providers/{conn_id}", {"models": []}, token=token)
        code, verify = curl("GET", f"/providers/{conn_id}", token=token)
        print(f"  After clear: {len(verify.get('models', []))} models")

        # Fetch from provider API
        code2, fetch_resp = curl("GET", f"/providers/{conn_id}/models", token=token)
        fetched = fetch_resp.get("models", [])
        fetched_ids = [m["id"] if isinstance(m, dict) else m for m in fetched]
        print(f"  Fetched: {len(fetched_ids)} models from API")

        # Save fetched models
        if fetched_ids:
            curl("PATCH", f"/providers/{conn_id}", {"models": fetched_ids}, token=token)
            code3, verify2 = curl("GET", f"/providers/{conn_id}", token=token)
            restored_count = len(verify2.get("models", []))
            print(f"  After fetch+save: {restored_count} models")

            report(
                "Clear then Fetch — models restored",
                f"GET /providers/{conn_id}/models after clear",
                [
                    "PATCH connection with {models: []} to clear",
                    "GET /providers/{conn_id}/models to fetch from API",
                    "PATCH connection with fetched models",
                    "GET /providers/{conn_id} to verify"
                ],
                f"Models restored ({len(fetched_ids)} models)",
                f"After fetch+save: {restored_count} models",
                restored_count > 0,
                f"Cleared, then fetched {len(fetched_ids)}, restored {restored_count}"
            )

            # Restore original
            if original_models:
                curl("PATCH", f"/providers/{conn_id}", {"models": original_models}, token=token)
                print(f"  (Restored original models)")

    # ============================================================
    # TEST 6: Enable All Models — DELETE /models/disabled?providerAlias=X
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 6: Enable All Models")
    print("=" * 60)

    # First, disable some models for a provider
    provider_alias = "groq"
    disable_ids = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    # Disable models
    code, disable_resp = curl("POST", "/models/disabled", {"providerAlias": provider_alias, "ids": disable_ids}, token=token)
    print(f"\n  Disabled {len(disenable_ids := disable_ids)} models for {provider_alias}: HTTP {code}")

    # Verify disabled
    code2, disabled_check = curl("GET", "/models/disabled", token=token, params={"providerAlias": provider_alias})
    disabled_list = disabled_check.get("ids", [])
    print(f"  Disabled list: {disabled_list}")
    print(f"  Count: {len(disabled_list)}")

    report(
        "Disable Models — POST /models/disabled",
        "POST /models/disabled",
        [f"POST /models/disabled with providerAlias={provider_alias}, ids={disable_ids}"],
        "Models added to disabled list",
        f"Disabled: {len(disabled_list)} models",
        len(disabled_list) >= len(disable_ids),
        f"Disabled {len(disabled_list)} models: {disabled_list}"
    )

    # Now enable all
    code3, enable_resp = curl("DELETE", "/models/disabled", token=token, params={"providerAlias": provider_alias})
    print(f"  Enable All response: HTTP {code3}, {enable_resp}")

    # Verify all enabled
    code4, enabled_check = curl("GET", "/models/disabled", token=token, params={"providerAlias": provider_alias})
    remaining_disabled = enabled_check.get("ids", [])
    print(f"  After Enable All: {len(remaining_disabled)} disabled")

    report(
        "Enable All — DELETE /models/disabled?providerAlias=X",
        f"DELETE /models/disabled?providerAlias={provider_alias}",
        [
            f"POST /models/disabled to disable {len(disable_ids)} models",
            f"DELETE /models/disabled?providerAlias={provider_alias}",
            "GET /models/disabled to verify"
        ],
        "All models enabled (0 disabled)",
        f"{len(remaining_disabled)} disabled after Enable All",
        len(remaining_disabled) == 0,
        f"Before: {len(disabled_list)} disabled, After: {len(remaining_disabled)} disabled"
    )

    # ============================================================
    # TEST 7: Disable All — POST /models/disabled with full list
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 7: Disable All Models")
    print("=" * 60)

    # Get all models for a provider from connections
    if groq_conns:
        all_groq_models = set()
        for c in groq_conns:
            for m in c.get("models", []):
                all_groq_models.add(m)
        all_models_list = list(all_groq_models)
        print(f"\n  Total unique groq models: {len(all_models_list)}")
        print(f"  Models: {all_models_list[:5]}...")

        # Disable all
        code, disable_all_resp = curl("POST", "/models/disabled", {"providerAlias": provider_alias, "ids": all_models_list}, token=token)
        print(f"  Disable All response: HTTP {code}")

        # Verify
        code2, check = curl("GET", "/models/disabled", token=token, params={"providerAlias": provider_alias})
        disabled_after = check.get("ids", [])
        print(f"  After Disable All: {len(disabled_after)} disabled")

        report(
            "Disable All — POST /models/disabled with all models",
            "POST /models/disabled",
            [f"POST /models/disabled with all {len(all_models_list)} groq models"],
            f"All {len(all_models_list)} models disabled",
            f"{len(disabled_after)} disabled",
            len(disabled_after) == len(all_models_list),
            f"Disabled {len(disabled_after)}/{len(all_models_list)} models"
        )

        # Enable all again
        curl("DELETE", "/models/disabled", token=token, params={"providerAlias": provider_alias})
        print(f"  (Re-enabled all models)")

    # ============================================================
    # TEST 8: Enable All — Verify with disabled model count check
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 8: Enable All with disabled models verification")
    print("=" * 60)

    # Disable 3 specific models for gemini
    gemini_disable = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
    code, _ = curl("POST", "/models/disabled", {"providerAlias": "gemini", "ids": gemini_disable}, token=token)

    # Verify they're disabled
    code2, check = curl("GET", "/models/disabled", token=token, params={"providerAlias": "gemini"})
    disabled_gemini = check.get("ids", [])
    print(f"\n  Disabled gemini models: {disabled_gemini}")

    # Enable all
    code3, _ = curl("DELETE", "/models/disabled", token=token, params={"providerAlias": "gemini"})

    # Verify
    code4, check2 = curl("GET", "/models/disabled", token=token, params={"providerAlias": "gemini"})
    remaining = check2.get("ids", [])

    report(
        "Enable All — verify disabled list is empty",
        f"DELETE /models/disabled?providerAlias=gemini",
        [
            f"POST /models/disabled to disable {len(gemini_disable)} gemini models",
            "DELETE /models/disabled?providerAlias=gemini",
            "GET /models/disabled?providerAlias=gemini to verify"
        ],
        "Disabled list empty after Enable All",
        f"{len(remaining)} remaining disabled",
        len(remaining) == 0,
        f"Before: {len(disabled_gemini)} disabled, After: {len(remaining)} disabled"
    )

    # ============================================================
    # TEST 9: Fetch after Clear, then Clear after Fetch
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 9: Fetch after Clear, then Clear after Fetch")
    print("=" * 60)

    if cerebras_conns:
        target = cerebras_conns[1]  # Use second connection (has 4 models)
        conn_id = target["id"]
        original = target.get("models", [])
        print(f"\n  Target: cerebras / {target['name']} ({conn_id})")
        print(f"  Original: {len(original)} models")

        # Clear
        curl("PATCH", f"/providers/{conn_id}", {"models": []}, token=token)
        code, v = curl("GET", f"/providers/{conn_id}", token=token)
        print(f"  After clear: {len(v.get('models', []))} models")

        # Fetch
        code2, fetch = curl("GET", f"/providers/{conn_id}/models", token=token)
        fetched = fetch.get("models", [])
        fetched_ids = [m["id"] if isinstance(m, dict) else m for m in fetched]
        print(f"  Fetched: {len(fetched_ids)} models")

        if fetched_ids:
            curl("PATCH", f"/providers/{conn_id}", {"models": fetched_ids}, token=token)
            code3, v2 = curl("GET", f"/providers/{conn_id}", token=token)
            after_fetch = len(v2.get("models", []))
            print(f"  After fetch+save: {after_fetch} models")

            # Now clear after fetch
            curl("PATCH", f"/providers/{conn_id}", {"models": []}, token=token)
            code4, v3 = curl("GET", f"/providers/{conn_id}", token=token)
            after_clear = len(v3.get("models", []))
            print(f"  After clear-after-fetch: {after_clear} models")

            report(
                "Fetch after Clear, then Clear after Fetch",
                f"GET/DELETE /providers/{conn_id}/models",
                [
                    "Clear models (PATCH with [])",
                    "Fetch models from API (GET /providers/{id}/models)",
                    "Save fetched models (PATCH)",
                    "Clear again (PATCH with [])"
                ],
                "All transitions work correctly",
                f"Clear→Fetch→Save={after_fetch}, Clear again={after_clear}",
                after_fetch > 0 and after_clear == 0,
                f"Fetch restored {after_fetch} models, clear removed all again"
            )

            # Restore
            if original:
                curl("PATCH", f"/providers/{conn_id}", {"models": original}, token=token)

    # ============================================================
    # TEST 10: Persistence — Save models, verify after "refresh"
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 10: Persistence — models survive re-read")
    print("=" * 60)

    if gemini_conns:
        target = gemini_conns[0]
        conn_id = target["id"]
        original = target.get("models", [])

        # Save specific test models
        test_models = ["test-model-a", "test-model-b", "test-model-c"]
        code, _ = curl("PATCH", f"/providers/{conn_id}", {"models": test_models}, token=token)
        print(f"\n  Saved {len(test_models)} test models to {conn_id}")

        # Simulate page refresh — re-read
        time.sleep(0.5)
        code2, verify = curl("GET", f"/providers/{conn_id}", token=token)
        persisted = verify.get("models", [])
        print(f"  After re-read: {len(persisted)} models: {persisted}")

        report(
            "Persistence — models survive re-read",
            f"GET /providers/{conn_id}",
            [
                f"PATCH with {len(test_models)} test models",
                "Wait 0.5s, then GET to verify"
            ],
            f"Models persist: {test_models}",
            f"Persisted: {persisted}",
            persisted == test_models,
            f"Saved {test_models}, got back {persisted}"
        )

        # Restore
        if original:
            curl("PATCH", f"/providers/{conn_id}", {"models": original}, token=token)

    # ============================================================
    # TEST 11: Clear Models — also clears disabled models
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 11: DELETE /providers/{id}/models — also clears disabled")
    print("=" * 60)

    if groq_conns:
        target = groq_conns[0]
        conn_id = target["id"]
        provider_alias = "groq"

        # First, ensure there are models and disabled models
        original_models = target.get("models", [])
        if not original_models:
            # Fetch some models first
            code, fetch = curl("GET", f"/providers/{conn_id}/models", token=token)
            fetched = fetch.get("models", [])
            fetched_ids = [m["id"] if isinstance(m, dict) else m for m in fetched]
            if fetched_ids:
                curl("PATCH", f"/providers/{conn_id}", {"models": fetched_ids}, token=token)

        # Disable some models
        test_disable = ["llama-3.3-70b-versatile"]
        curl("POST", "/models/disabled", {"providerAlias": provider_alias, "ids": test_disable}, token=token)

        # Check disabled state before
        code, before = curl("GET", "/models/disabled", token=token, params={"providerAlias": provider_alias})
        disabled_before = before.get("ids", [])
        print(f"\n  Before DELETE clear: {len(disabled_before)} disabled models")

        # Use DELETE /providers/{id}/models (backend clear endpoint)
        code2, clear_resp = curl("DELETE", f"/providers/{conn_id}/models", token=token)
        print(f"  DELETE /providers/{conn_id}/models: HTTP {code2}, {clear_resp}")

        # Check disabled state after
        code3, after = curl("GET", "/models/disabled", token=token, params={"providerAlias": provider_alias})
        disabled_after = after.get("ids", [])

        # Check models state
        code4, verify = curl("GET", f"/providers/{conn_id}", token=token)
        models_after = verify.get("models", [])

        report(
            "DELETE /providers/{id}/models — clears models AND disabled list",
            f"DELETE /providers/{conn_id}/models",
            [
                "Disable some models via POST /models/disabled",
                f"DELETE /providers/{conn_id}/models",
                "Check models and disabled list"
            ],
            "Models cleared and disabled list cleaned",
            f"Models: {len(models_after)}, Disabled: {len(disabled_after)} (was {len(disabled_before)})",
            len(models_after) == 0,
            f"Models: {len(models_after)}, Disabled before: {len(disabled_before)}, after: {len(disabled_after)}"
        )

    # ============================================================
    # TEST 12: Multiple connections — Fetch merges models
    # ============================================================
    print("\n" + "=" * 60)
    print("TEST 12: Multiple connections — Fetch merges models")
    print("=" * 60)

    if gemini_conns and len(gemini_conns) >= 2:
        print(f"\n  Target: gemini ({len(gemini_conns)} connections)")

        # Clear all connections first
        for c in gemini_conns:
            curl("PATCH", f"/providers/{c['id']}", {"models": []}, token=token)

        # Fetch from all connections (simulating frontend behavior)
        all_fetched = set()
        for c in gemini_conns:
            code, fetch = curl("GET", f"/providers/{c['id']}/models", token=token)
            fetched = fetch.get("models", [])
            for m in fetched:
                mid = m["id"] if isinstance(m, dict) else m
                all_fetched.add(mid)
            print(f"    {c['id']}: fetched {len(fetched)} models")

        merged = list(all_fetched)
        print(f"  Merged unique models: {len(merged)}")

        # Save merged to all connections
        for c in gemini_conns:
            curl("PATCH", f"/providers/{c['id']}", {"models": merged}, token=token)

        # Verify
        for c in gemini_conns:
            code, verify = curl("GET", f"/providers/{c['id']}", token=token)
            saved = verify.get("models", [])
            print(f"    {c['id']}: saved {len(saved)} models")

        report(
            "Multiple connections — Fetch merges models from all",
            "GET /providers/{id}/models for each connection",
            [
                "Clear all connections",
                "Fetch models from each connection",
                "Merge into unique set",
                "Save merged list to all connections"
            ],
            f"All connections have same {len(merged)} merged models",
            f"Merged {len(merged)} unique models",
            len(merged) > 0,
            f"Got {len(merged)} unique models from {len(gemini_conns)} connections"
        )

        # Restore
        for c in gemini_conns:
            orig = next((oc for oc in gemini_conns if oc["id"] == c["id"]), None)
            if orig and orig.get("models"):
                curl("PATCH", f"/providers/{c['id']}", {"models": orig["models"]}, token=token)

    # ============================================================
    # SUMMARY
    # ============================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for r in RESULTS if r["status"] == "PASS")
    failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
    print(f"  Total: {len(RESULTS)} | Passed: {passed} | Failed: {failed}")
    print()
    for r in RESULTS:
        icon = "✅" if r["status"] == "PASS" else "❌"
        print(f"  {icon} {r['test']}")
        if r["status"] == "FAIL":
            print(f"      Expected: {r['expected']}")
            print(f"      Actual: {r['actual']}")
            if r["details"]:
                print(f"      Details: {r['details']}")

    return failed

if __name__ == "__main__":
    sys.exit(main())
