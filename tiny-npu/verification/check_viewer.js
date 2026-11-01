// Offline viewer smoke test without network or DOM packages.
const fs=require('fs'),vm=require('vm');
const text=fs.readFileSync(process.argv[2],'utf8');
const script=text.match(/<script>([\s\S]*)<\/script>/)[1];
const elements={},calls={rect:0,text:0};
function el(id){return elements[id]??=(id==='plot'?{clientWidth:1200,width:1200,height:600,getContext:()=>({clearRect(){},fillText(){calls.text++},beginPath(){},moveTo(){},lineTo(){},stroke(){},fillRect(){calls.rect++}}),getBoundingClientRect(){return {left:0,top:0,width:1200,height:this.height}}}:{value:id==='start'?0:'',innerHTML:'',textContent:''})}
const context={document:{getElementById:el},window:{},console};vm.createContext(context);vm.runInContext(script,context,{timeout:10000});
if(!calls.rect||!calls.text||!el('scope').textContent)throw Error('viewer did not render');
let before=+el('window').value;el('zin').onclick();if(+el('window').value>=before)throw Error('zoom failed');
el('filter').value='rocket.h7';el('filter').oninput();el('all').onclick();
el('bubbles').onclick({target:{closest:()=>({dataset:{i:'0'}})}});
console.log('VIEWER_PASS draw/zoom/filter/bubble-focus',calls);
