// SPDX-License-Identifier: Apache-2.0
(() => {
    const d = desktopClient.getDisplay(), s = $('screen').getBoundingClientRect();
    const viewport = $('screen-scroll').getBoundingClientRect();
    // Pre-M128 CSS zoom reports rectangles in unzoomed coordinates. Detect
    // actual semantics rather than inferring them from a provider version.
    const probe = document.createElement('div');
    probe.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;zoom:.5;visibility:hidden;pointer-events:none';
    document.body.appendChild(probe);
    const legacyZoomCoordinates = Math.abs(probe.getBoundingClientRect().width - 20) < .1;
    probe.remove();
    const layer = d.getElement().firstElementChild;
    const factor = legacyZoomCoordinates ? Number(getComputedStyle(layer).zoom) || 1 : 1;
    const normalize = element => {
        const b = element.getBoundingClientRect();
        return {x:b.x*factor,y:b.y*factor,width:b.width*factor,height:b.height*factor};
    };
    const root = normalize(layer), cursor = normalize(d.getCursorLayer().getElement());
    const toggle = $('desk-controls'), control = toggle.getBoundingClientRect();
    const box = b => [b.x, b.y, b.width, b.height].map(n => Math.round(n * 100) / 100);
    const close = (a, b) => Math.abs(a - b) < 1.5;
    return {
        viewport: [innerWidth, innerHeight], frame: box(s), container: box(viewport),
        legacyZoomCoordinates, overlay: toggle.hidden ? [0,0,0,0] : box(control),
        content: box(root), remote: [d.getWidth(), d.getHeight()], scale: d.getScale(),
        fullscreen: fullscreenDesktop, presentation: desktopScaling.mode,
        fit: s.width > 0 && s.height > 0 && s.width <= viewport.width + 1.5
            && s.height <= viewport.height + 1.5 && s.x >= -1.5 && s.y >= -1.5
            && s.right <= innerWidth + 1.5 && s.bottom <= innerHeight + 1.5,
        centered: close(s.x + s.width / 2, viewport.x + viewport.width / 2)
            && close(s.y + s.height / 2, viewport.y + viewport.height / 2),
        contentAligned: close(s.x, root.x) && close(s.y, root.y)
            && close(s.width, root.width) && close(s.height, root.height)
            && close(root.width, d.getWidth() * d.getScale())
            && close(root.height, d.getHeight() * d.getScale()),
        cursorAligned: close(cursor.x - s.x, (d.cursorX - 3) * d.getScale())
            && close(cursor.y - s.y, (d.cursorY - 4) * d.getScale()),
        errors: window.__compatErrors
    };
})()
