// Landing hero animation initializer
(function(){
  function prefersReducedMotion(){ return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches; }

  function init(){
    const hero = document.querySelector('.glass-card--hero');
    if(!hero) return;
    const headline = hero.querySelector('h1, .hero-headline');
    const paragraph = hero.querySelector('p');
    const ctas = hero.querySelectorAll('.btn');
    const img = hero.querySelector('img');

    // add helper classes
    if(headline) headline.classList.add('hero-animate-child');
    if(paragraph) paragraph.classList.add('hero-animate-child');
    ctas.forEach((b)=> b.classList.add('hero-animate-child'));
    if(img) img.classList.add('hero-illustration');

    if(prefersReducedMotion()){
      // reveal without motion
      hero.classList.add('hero-animated');
      if(headline) headline.style.opacity = 1;
      if(paragraph) paragraph.style.opacity = 1;
      ctas.forEach(b=> b.style.opacity = 1);
      return;
    }

    // staggered animation
    setTimeout(()=>{
      hero.classList.add('hero-animated');
      if(headline) headline.style.setProperty('--delay','0ms');
      if(paragraph) paragraph.style.setProperty('--delay','140ms');
      ctas.forEach((b,i)=> b.style.setProperty('--delay', (260 + i*120) + 'ms'));
    }, 120);
  }

  document.addEventListener('DOMContentLoaded', init);
})();
