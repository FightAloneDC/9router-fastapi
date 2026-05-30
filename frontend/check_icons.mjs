import { createRequire } from 'module';
const require = createRequire(import.meta.url);

const pkg = require('lucide-react/package.json');
console.log('version:', pkg.version);
console.log('exports:', Object.keys(pkg.exports || {}).slice(0, 5));

// Check icon existence
const icons = ['Beaker','Cookie','Lock','Warning','Info','OpenInNew','Lan','Block','RestartAlt','ToggleLeft','ToggleRight','Expand','Settings2','Zap','Shield','Globe','Shuffle','Play','ChevronUp','ChevronDown','CheckCircle2','AlertCircle','Loader2','Wifi','Edit2','ExternalLink','X','Copy','Check','ArrowLeft','Plus','Trash2','Key','Eye','EyeOff','Download','Add'];
for (const icon of icons) {
  try {
    const mod = require(`lucide-react/dist/esm/icons/${icon.toLowerCase()}.js`);
    console.log(icon + ': OK');
  } catch {
    try {
      // Check if it's in the main export
      const main = require('lucide-react');
      console.log(icon + ': ' + (icon in main ? 'OK' : 'MISSING'));
    } catch(e2) {
      console.log(icon + ': CHECK_FAILED');
    }
  }
}
