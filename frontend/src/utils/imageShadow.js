// Presentation only: preserve the source image and its geometry.
export function imageShadowStyle(shadow) {
  if (!shadow || typeof shadow !== 'object') return {};
  const presets = {soft:[16,6,18],medium:[24,10,28],strong:[32,14,40]};
  if (shadow.preset === 'none' || !['soft','medium','strong','custom'].includes(shadow.preset)) return {filter:'none',boxShadow:'none'};
  const defaults = presets[shadow.preset] || presets.soft;
  const number = (value, fallback, min, max) => typeof value === 'number' && Number.isFinite(value) ? Math.min(max,Math.max(min,value)) : fallback;
  const blur=number(shadow.blur,defaults[0],0,60),x=number(shadow.x,0,-40,40),y=number(shadow.y,defaults[1],-40,40);
  const opacity=number(shadow.opacity,defaults[2],0,70)/100;
  const color=typeof shadow.color==='string' && /^#[0-9a-f]{6}$/i.test(shadow.color) ? shadow.color : '#000000';
  const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)).join(',');
  const css=`${x}px ${y}px ${blur}px rgba(${rgb},${opacity})`;
  return shadow.mode === 'frame' ? {boxShadow:css,filter:'none'} : {filter:`drop-shadow(${css})`,boxShadow:'none'};
}

export function imageShadowPreset(preset) {
  const values={soft:[16,6,18],medium:[24,10,28],strong:[32,14,40]};
  const [blur,y,opacity]=values[preset] || values.soft;
  return {preset,mode:'contour',color:'#000000',blur,x:0,y,opacity};
}
