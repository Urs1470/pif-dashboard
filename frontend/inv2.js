import('./src/lib/driveCalc.js').then(m => {
  const mods = m.MODULES;
  const MODULE_ORDER = m.MODULE_ORDER;
  const APP_OF = m.APP_OF;
  const catOf = m.catOf;
  
  // Find modules that fall into 'aplicatii' category
  const sysTabCategories = ['vfd', 'armonici', 'instalatie', 'termic', 'utilitare'];
  const appModuleIds = new Set();
  const motorModuleIds = new Set();
  
  MODULE_ORDER.forEach(modId => {
    const mod = mods.find(m => m.id === modId);
    if (mod) {
      const cat = catOf(mod);
      if (cat === 'aplicatii') {
        appModuleIds.add(mod.id);
      } else if (cat === 'motoare') {
        motorModuleIds.add(mod.id);
      }
    }
  });
  
  console.log('=== MODULES NOT IN SYSTEM TABS ===');
  console.log('');
  console.log('APLICATII (' + appModuleIds.size + ' modules):');
  appModuleIds.forEach(id => {
    const mod = mods.find(m => m.id === id);
    if (mod) {
      console.log(id + ' | ' + mod.title + ' | ' + mod.family);
    }
  });
  
  console.log('');
  console.log('MOTOARE (' + motorModuleIds.size + ' modules):');
  motorModuleIds.forEach(id => {
    const mod = mods.find(m => m.id === id);
    if (mod) {
      console.log(id + ' | ' + (mod.title || '') + ' | ' + (mod.family || ''));
    }
  });
  
}).catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
