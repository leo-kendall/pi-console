// SPDX-License-Identifier: Apache-2.0
// Only the transport/paired state are synthetic. Keep local()/Pi and real
// Guacamole decoding, display, input layout, WebView and native window helpers.
window.__compatErrors = 0;
addEventListener('error', () => { window.__compatErrors++; });
addEventListener('unhandledrejection', () => { window.__compatErrors++; });
window.__compatFrame = (...parts) => parts.map(p => String(p).length + '.' + p).join(',') + ';';
window.__compatColor = (w, h) => {
    const first = Math.floor(w / 3), second = Math.floor(2 * w / 3);
    return __compatFrame('size', 0, w, h)
        + __compatFrame('rect', 0, 0, 0, w, h)
        + __compatFrame('cfill', 14, 0, 31, 177, 107, 255)
        + __compatFrame('rect', 0, first, 0, second - first, h)
        + __compatFrame('cfill', 14, 0, 40, 120, 220, 255)
        + __compatFrame('rect', 0, second, 0, w - second, h)
        + __compatFrame('cfill', 14, 0, 220, 130, 40, 255)
        + __compatFrame('sync', 1);
};
window.__compatIncoming = '';
window.__compatOpened = null;
window.__compatSizes = [];
const compatWrites = new Guacamole.Parser();
compatWrites.oninstruction = (opcode, args) => {
    if (opcode !== 'size') return;
    const width = Number(args[0]), height = Number(args[1]);
    if (args.length !== 2 || !Number.isInteger(width) || !Number.isInteger(height)
        || width < 320 || width > 2560 || height < 200 || height > 1440)
        throw new Error('Invalid compatibility resize request');
    __compatSizes.push([width, height]);
    // Only an actual outbound request may produce a new remote size.
    __compatIncoming += __compatColor(width, height);
};
window.__compatReads = 0;
window.__compatTransportCalls = 0;
api = async (path, body) => {
    window.__compatTransportCalls++;
    if (path === '/api/desktop/open') {
        window.__compatOpened = {width: body.width, height: body.height};
        __compatIncoming = __compatColor(body.width, body.height);
        return {id: 'offline-compat', protocol: 'rdp'};
    }
    if (path.startsWith('/api/desktop/write/')) compatWrites.receive(body.data);
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
