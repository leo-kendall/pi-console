// SPDX-License-Identifier: Apache-2.0
// Only the transport/paired state are synthetic. Keep local()/Pi and real
// Guacamole decoding, display, input layout, WebView and native window helpers.
window.__compatErrors = 0;
addEventListener('error', () => { window.__compatErrors++; });
addEventListener('unhandledrejection', () => { window.__compatErrors++; });
window.__compatFrame = (...parts) => parts.map(p => String(p).length + '.' + p).join(',') + ';';
window.__compatColor = (w, h) => __compatFrame('size', 0, w, h)
    + __compatFrame('rect', 0, 0, 0, w, h)
    + __compatFrame('cfill', 14, 0, 31, 177, 107, 255)
    + __compatFrame('sync', 1);
window.__compatIncoming = __compatColor(1280, 800);
window.__compatReads = 0;
window.__compatTransportCalls = 0;
api = async (path, body) => {
    window.__compatTransportCalls++;
    if (path === '/api/desktop/open') return {id: 'offline-compat', protocol: 'rdp'};
    if (path.startsWith('/api/desktop/read/')) {
        await new Promise(resolve => setTimeout(resolve, 60));
        const data = window.__compatIncoming;
        window.__compatIncoming = '';
        return {data: data + __compatFrame('sync', ++window.__compatReads)};
    }
    return {ok: true};
};
paired = true;
navigate('desktop');
$('resolution').value = '1280,800';
$('desktop-connect').click();
true;
