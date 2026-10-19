// Pure, self-contained: serialized into the offline assessment player as well.
export function assessmentVideoLink(raw) {
  const invalid = () => { throw new Error('Use um link HTTPS de vídeo do YouTube, Vimeo ou Bunny Stream (não cole código HTML).'); };
  if (typeof raw !== 'string' || raw.length > 4000 || /[<>\\\u0000-\u0020]/.test(raw.trim())) return invalid();
  let u;
  try { u = new URL(raw.trim()); } catch { return invalid(); }
  if (u.protocol !== 'https:' || u.username || u.password || u.port) return invalid();
  const host = u.hostname.toLowerCase();
  const p = u.pathname;
  let id;
  if (['youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be', 'www.youtube-nocookie.com', 'youtube-nocookie.com'].includes(host)) {
    id = host === 'youtu.be' ? p.slice(1) : p === '/watch' ? u.searchParams.get('v') : p.match(/^\/(?:embed|shorts|live)\/([\w-]+)\/?$/)?.[1];
    if (!id || !/^[A-Za-z0-9_-]{11}$/.test(id)) return invalid();
    const result = new URL(`https://www.youtube-nocookie.com/embed/${id}`);
    const start = u.searchParams.get('start') || u.searchParams.get('t');
    if (start && /^\d+s?$/.test(start)) result.searchParams.set('start', start.replace(/s$/, ''));
    return { provider: 'YouTube', url: result.href };
  }
  if (['vimeo.com', 'www.vimeo.com', 'player.vimeo.com'].includes(host)) {
    const match = p.match(/^\/(?:video\/)?(\d+)(?:\/([A-Za-z0-9]+))?\/?$/);
    if (!match) return invalid();
    const result = new URL(`https://player.vimeo.com/video/${match[1]}`);
    const hash = u.searchParams.get('h') || match[2];
    if (hash) { if (!/^[A-Za-z0-9]+$/.test(hash)) return invalid(); result.searchParams.set('h', hash); }
    return { provider: 'Vimeo', url: result.href };
  }
  if (['iframe.mediadelivery.net', 'player.mediadelivery.net'].includes(host)) {
    const match = p.match(/^\/(?:embed|play)\/(\d+)\/([a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12})\/?$/);
    if (!match) return invalid();
    u.pathname = `/embed/${match[1]}/${match[2]}`;
    u.hash = ''; u.searchParams.set('autoplay', 'false');
    return { provider: 'Bunny Stream', url: u.href };
  }
  return invalid();
}
