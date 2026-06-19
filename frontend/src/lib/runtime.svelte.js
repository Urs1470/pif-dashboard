// Stare runtime partajata (reactiva, Svelte 5).
// docsOk = afiseaza linkurile catre extrasele de carti cu drept de autor (protected:true).
// Implicit TRUE: in dashboard (mereu in spatele login-ului) extrasele se vad.
// Pe /calc public, calc-main.js seteaza docsOk=false si il pune true doar daca esti autentificat
// (verificare /api/me), ca sa nu expuna extrasele colegilor anonimi.
export const runtime = $state({ docsOk: true })
