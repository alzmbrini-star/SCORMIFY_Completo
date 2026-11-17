/** Use one uniform scale for the slide, its images, and live video overlays. */
export function fitVideoRect(sourceW, sourceH, targetW, targetH, mode = 'contain') {
  const width = Number(sourceW), height = Number(sourceH);
  if (!(width > 0 && height > 0 && Number.isFinite(width) && Number.isFinite(height))) {
    throw new Error('Dimensões inválidas para exportar o slide ou a imagem.');
  }
  const scale = mode === 'cover' ? Math.max(targetW / width, targetH / height) : Math.min(targetW / width, targetH / height);
  return {x:(targetW-width*scale)/2, y:(targetH-height*scale)/2, width:width*scale, height:height*scale, scale};
}

export function fitExportImage(image, width, height, mode = 'contain') {
  // html2canvas does not reliably reproduce object-fit. Use actual dimensions
  // instead of giving the bitmap unequal horizontal and vertical scales.
  const rect = fitVideoRect(image.naturalWidth, image.naturalHeight, width, height, mode);
  Object.assign(image.style, {position:'absolute', inset:'auto', left:`${rect.x}px`, top:`${rect.y}px`,
    width:`${rect.width}px`, height:`${rect.height}px`, maxWidth:'none', maxHeight:'none', objectFit:'fill'});
  return rect;
}
