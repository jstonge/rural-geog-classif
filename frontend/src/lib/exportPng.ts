export async function exportPng(
  node: HTMLElement | SVGElement | null,
  filename: string,
  header?: HTMLElement | null
) {
  if (!node) return;
  // @ts-expect-error — dom-to-image-more has no bundled types
  const { default: domtoimage } = await import('dom-to-image-more');

  let target: HTMLElement | SVGElement = node;
  let cleanup: (() => void) | undefined;

  if (header) {
    const wrapper = document.createElement('div');
    wrapper.style.cssText =
      'background: white; padding: 16px; display: inline-block; font-family: system-ui, sans-serif;';
    wrapper.appendChild(header.cloneNode(true));
    wrapper.appendChild(node.cloneNode(true));
    document.body.appendChild(wrapper);
    target = wrapper;
    cleanup = () => wrapper.remove();
  }

  try {
    const dataUrl: string = await domtoimage.toPng(target, { bgcolor: 'white' });
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = filename.endsWith('.png') ? filename : `${filename}.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
  } finally {
    cleanup?.();
  }
}
