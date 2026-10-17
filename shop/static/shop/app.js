document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  const text = document.getElementById(button.dataset.copy);
  try { await navigator.clipboard.writeText(text.value); button.textContent = button.dataset.copied; }
  catch { text.focus(); text.select(); }
}));
const observer = new IntersectionObserver(entries => entries.forEach(entry => {
  if (!entry.isIntersecting) entry.target.pause();
}), {threshold: .5});
document.querySelectorAll('video').forEach(video => {
  observer.observe(video);
  video.addEventListener('play', () => document.querySelectorAll('video').forEach(other => { if (other !== video) other.pause(); }));
});
