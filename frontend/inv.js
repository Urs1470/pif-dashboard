import('./src/lib/driveCalc.js').then(m => {
  const mods = m.MODULES;
  const MODULE_ORDER = m.MODULE_ORDER;
  const catOf = m.catOf;
  
  // ========== INVENTORY 1: Field keys per machine family ==========
  const families = ['asincron', 'cc', 'servo', 'sincron', 'transformator'];
  const familyFields = {};
  
  families.forEach(fam => {
    const fieldMap = new Map();
    
    mods.forEach(mod => {
      if (mod.family === fam && mod.fields) {
        mod.fields.forEach(f => {
          if (!fieldMap.has(f.key)) {
            fieldMap.set(f.key, {
              key: f.key,
              unit: f.unit || '',
              default: f.default !== undefined ? f.default : '',
              label: f.label || '',
              count: 0
            });
          }
          fieldMap.get(f.key).count++;
        });
      }
    });
    
    familyFields[fam] = Array.from(fieldMap.values()).sort((a, b) => b.count - a.count);
  });
  
  console.log('=== INVENTORY 1: FIELD KEYS PER MACHINE FAMILY ===');
  families.forEach(fam => {
    const fields = familyFields[fam];
    console.log('');
    console.log(fam.toUpperCase() + ' (' + fields.length + ' distinct fields):');
    console.log('key | unit | default | label | count');
    fields.forEach(f => {
      const def = f.default !== '' ? String(f.default) : '—';
      console.log(f.key + ' | ' + (f.unit || '—') + ' | ' + def + ' | ' + (f.label || '—') + ' | ' + f.count);
    });
  });
  
  // ========== INVENTORY 2: Modules per system tab ==========
  const categories = ['vfd', 'armonici', 'instalatie', 'termic', 'utilitare'];
  const modulesPerCat = {};
  
  categories.forEach(cat => {
    modulesPerCat[cat] = [];
  });
  
  MODULE_ORDER.forEach(modId => {
    const mod = mods.find(m => m.id === modId);
    if (mod) {
      const cat = catOf(mod);
      if (categories.includes(cat)) {
        modulesPerCat[cat].push({
          id: mod.id,
          title: mod.title || '',
          family: mod.family || ''
        });
      }
    }
  });
  
  console.log('');
  console.log('');
  console.log('=== INVENTORY 2: MODULES PER SYSTEM TAB ===');
  categories.forEach(cat => {
    const items = modulesPerCat[cat];
    console.log('');
    console.log(cat.toUpperCase() + ' (' + items.length + ' modules):');
    console.log('id | title | family');
    items.forEach(item => {
      console.log(item.id + ' | ' + item.title + ' | ' + item.family);
    });
  });
  
}).catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
