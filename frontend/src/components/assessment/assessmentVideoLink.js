// Pure, self-contained: serialized into the offline assessment player as well.
export function assessmentVideoLink(raw) {
  const invalid = () => { throw new Error('Use um link HTTPS de vídeo ou o iframe completo do Bunny, Vimeo ou YouTube.'); };
  if (typeof raw !== 'string' || raw.length > 16000) return invalid();
  // Extract data only. Never render pasted HTML, scripts or event handlers.
  const iframe = raw.match(/<iframe\b[^>]*\bsrc\s*=\s*(["'])(.*?)\1/is);
  raw = (iframe ? iframe[2] : raw).trim().replace(/&(?:amp|#0*38|#x0*26);/gi, '&');
  if (raw.length > 4000 || /[<>\\\u0000-\u0020]/.test(raw)) return invalid();
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
    // Match the Editor: preserve the signed URL byte-for-byte. Rebuilding the
    // path/query (including autoplay or play→embed) can invalidate signatures.
    return { provider: 'Bunny Stream', url: raw };
  }
  return invalid();
}
