export async function exportPng(node: HTMLElement | SVGElement | null, filename: string) {
  if (!node) return;
  // @ts-expect-error — dom-to-image-more has no bundled types
  const { default: domtoimage } = await import('dom-to-image-more');
  const dataUrl: string = await domtoimage.toPng(node, { bgcolor: 'white' });
  const link = document.createElement('a');
  link.href = dataUrl;
  link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
  document.body.appendChild(link);
  link.click();
  link.remove();
}
