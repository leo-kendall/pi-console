// SPDX-License-Identifier: Apache-2.0
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const controls = {resolution: {value: ''}, 'desktop-connect': {click() {}}};
const c = {window: null, addEventListener() {}, setTimeout, clearTimeout,
    navigator: {}, document: {}, $: id => controls[id], navigate() {}, paired: false, api: null};
c.window = c;
vm.createContext(c);
vm.runInContext(fs.readFileSync(__dirname + '/../android/assets/guacamole.js', 'utf8'), c);
vm.runInContext(fs.readFileSync(__dirname + '/../android/compat/assets/setup.js', 'utf8'), c);

function geometry(legacy, scaleError = 1, cursorError = 0) {
    const s = {x:20, y:200, width:640, height:400, right:660, bottom:600};
    const factor = legacy ? 2 : 1;
    const element = b => ({getBoundingClientRect: () => b});
    const layer = element({x:20*factor,y:200*factor,width:640*factor*scaleError,height:400*factor*scaleError});
    const cursor = element({x:(338.5+cursorError)*factor,y:398*factor,width:8*factor,height:8*factor});
    const d = {getElement:()=>({firstElementChild:layer}),getCursorLayer:()=>({getElement:()=>cursor}),
        getWidth:()=>1280,getHeight:()=>800,getScale:()=>.5,cursorX:640,cursorY:400};
    const elements = {'screen':element(s),'screen-scroll':element(s),'desk-controls':element({x:610,y:0,width:50,height:50})};
    const context = {desktopClient:{getDisplay:()=>d},$:id=>elements[id],innerWidth:800,innerHeight:700,
        fullscreenDesktop:false,desktopScaling:{mode:'layout'},window:{__compatErrors:0},
        getComputedStyle:()=>({zoom:'.5'}), document:{body:{appendChild(){}},createElement:()=>({style:{},
            getBoundingClientRect:()=>({width:legacy?20:10}),remove(){}})}};
    return vm.runInNewContext(fs.readFileSync(__dirname + '/../android/compat/assets/geometry.js','utf8'),context);
}
for (const legacy of [false,true]) {
    const good = geometry(legacy);
    assert.equal(good.legacyZoomCoordinates,legacy);
    assert.equal(good.contentAligned,true);
    assert.equal(good.cursorAligned,true);
    assert.equal(geometry(legacy,2).contentAligned,false,'Cropping/unscaled content must fail on either coordinate convention');
    assert.equal(geometry(legacy,1,10).cursorAligned,false,'A shifted cursor must fail on either convention');
}

(async () => {
    await c.api('/api/desktop/open',{width:1280,height:800});
    assert.equal(c.__compatOpened.width,1280);
    c.__compatIncoming = '';
    await c.api('/api/desktop/write/offline-compat',{data:c.__compatFrame('key',65,1)});
    assert.equal(c.__compatIncoming,'','Unrelated input cannot acknowledge a resize');
    const command = c.__compatFrame('size',2560,1440);
    await c.api('/api/desktop/write/offline-compat',{data:command.slice(0,10)});
    assert.equal(c.__compatIncoming,'','Incomplete protocol input cannot acknowledge a resize');
    await c.api('/api/desktop/write/offline-compat',{data:command.slice(10)});
    assert(c.__compatIncoming.includes('2560'),'Actual outbound resize must drive acknowledgement');
    const received = [];
    const parser = new c.Guacamole.Parser();
    parser.oninstruction = (opcode,args) => received.push([opcode,...args]);
    parser.receive(c.__compatIncoming);
    assert.equal(received.filter(row=>row[0]==='cfill').length,3,'Three color bands must detect cropped/unscaled frames');
    await assert.rejects(c.api('/api/desktop/write/offline-compat',{data:c.__compatFrame('size',4096,1440)}));
    console.log('Compatibility fixtures verify protocol-driven resize and both CSS zoom coordinate conventions');
})().catch(error => { console.error(error); process.exitCode=1; });
