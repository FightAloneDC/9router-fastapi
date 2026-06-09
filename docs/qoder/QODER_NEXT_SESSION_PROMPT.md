# Prompt Sesi Baru: Qoder Provider Investigation

Kamu bekerja di repo `/home/mint/dev/9router-fastapi`.

Instruksi penting:

- Jangan edit/create file tanpa instruksi eksplisit user.
- Untuk Qoder, jangan asumsi. Baca fakta di `QODER_PROVIDER_DOC.md`, terutama Section 15.
- Qoder punya dua metode add connection yang valid: PAT import dan OAuth/device flow.
- Jangan menyimpulkan PAT rusak atau harus diganti OAuth. PAT baru sudah terbukti berhasil.
- Jangan membuat rekomendasi auth method kecuali berdasarkan bukti per-connection.

Fakta lapangan terakhir:

1. Backup folder Qoder sudah dibuat:

   `backups/qoder-provider-backup-20260609-163719.tar.gz`

2. Last recorded commit sebelum investigasi:

   `ca68b4f65a6e80021fe3f450ece3e4e888330be0`

3. Qoder connection via PAT menyimpan data seperti:

   - `accessToken`: `jt-...`
   - `refreshToken`: `jrt-...`
   - `userId`
   - `machineId` auto-generated per connection
   - `loginMethod`: `pat`

4. Connection PAT baru profile `HanawatiBafasari bose` berhasil fetch model:

   - provider: `qoder`
   - auth_type: `apikey`
   - accessToken prefix: `jt-JSb...`
   - machineId: `dae03950-b0ba-44f1-b9c9-2399cce7fca1`
   - fetch models: HTTP 200 OK
   - 11 models persisted

5. Connection lama `Manda Mora` sebelumnya mengalami:

   - fetch models: HTTP 403
   - upstream body: `{"code":"105","message":"Login expired"}`
   - direct userinfo check saat investigasi: `401 TOKEN_EXPIRE / token is not active`

   Ini hanya bukti untuk token/connection lama tersebut. Jangan generalisasi ke semua PAT.

6. qodercli capture menunjukkan Qoder memakai beberapa bentuk auth tergantung endpoint:

   - beberapa endpoint account/status/region memakai plain bearer/signature
   - endpoint `/algo` service seperti chat generation memakai `Authorization: Bearer COSY.{payloadB64}.{sig}`

   Jadi `Bearer COSY` bukan otomatis salah untuk endpoint `/algo`.

7. Dokumen `QODER_PROVIDER_DOC.md` sudah dikoreksi agar menyatakan fakta di atas.

Status perubahan file dari investigasi sebelumnya mungkin ada di:

- `QODER_PROVIDER_DOC.md`
- `backend/app/providers/qoder/constants.py`
- `backend/app/providers/qoder/cosy.py`
- `backend/app/providers/qoder/handler.py`
- `backend/tests/test_qoder_cosy.py`
- `backups/qoder-provider-backup-20260609-163719.tar.gz`

Sebelum lanjut coding, lakukan audit singkat:

```bash
git status --short
git diff -- QODER_PROVIDER_DOC.md backend/app/providers/qoder/constants.py backend/app/providers/qoder/cosy.py backend/app/providers/qoder/handler.py backend/tests/test_qoder_cosy.py
```

Jika user meminta fix Qoder, langkah read-only yang aman:

1. Compare DB data connection lama vs connection PAT baru yang berhasil.
2. Test `fetch_qoder_catalog()` untuk connection yang gagal dan yang berhasil.
3. Jangan ubah auth flow PAT/OAuth tanpa bukti.
4. Jika perlu rollback perubahan kode Qoder, gunakan backup folder, jangan reset seluruh repo.

Tujuan sesi baru:

- Agent langsung paham bahwa PAT dan OAuth sama-sama valid.
- Agent tidak mengulang kesalahan menyimpulkan PAT tidak bisa.
- Agent fokus pada per-connection token/state, signer/header, refresh behavior, atau UI stale state berdasarkan bukti.
