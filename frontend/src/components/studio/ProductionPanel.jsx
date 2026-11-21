import { useEffect, useRef, useState } from "react";

const field = "w-full rounded-lg bg-white/5 border border-white/10 p-2 text-sm";
const btn = "rounded-full border border-white/15 px-3 py-2 text-sm disabled:opacity-40";
const defaults = { scene:"camera", title:"", ticker:"", logo:"LoNo" };
const choices = [["camera","Camera"],["screen","Screen share"],["pip","Screen + camera"],["clip","Prerecorded file"],["slate","Station slate"]];

function fit(ctx, video, x, y, w, h) {
  if (!video || video.readyState<2 || !video.videoWidth) return;
  const scale=Math.min(w/video.videoWidth,h/video.videoHeight);
  const width=video.videoWidth*scale,height=video.videoHeight*scale;
  ctx.drawImage(video,x+(w-width)/2,y+(h-height)/2,width,height);
}
function draw(canvas, scene, camera, screen, clip) {
  const ctx=canvas.getContext("2d"),w=canvas.width,h=canvas.height;
  ctx.fillStyle="#101010";ctx.fillRect(0,0,w,h);
  if(scene.scene==="camera")fit(ctx,camera,0,0,w,h);
  else if(scene.scene==="screen"||scene.scene==="pip") {fit(ctx,screen,0,0,w,h);if(scene.scene==="pip"){ctx.fillStyle="#000";ctx.fillRect(w-330,20,310,180);fit(ctx,camera,w-330,20,310,180);}}
  else if(scene.scene==="clip")fit(ctx,clip,0,0,w,h);
  else {ctx.fillStyle="#fff";ctx.font="bold 64px sans-serif";ctx.textAlign="center";ctx.fillText(scene.logo||"LoNo",w/2,h/2,w-60);ctx.textAlign="left";}
  if(scene.logo){ctx.fillStyle="#b52620";ctx.fillRect(20,20,220,52);ctx.fillStyle="#fff";ctx.font="bold 28px sans-serif";ctx.fillText(scene.logo,30,55,200);}
  if(scene.title){ctx.fillStyle="rgba(0,0,0,.85)";ctx.fillRect(20,h-148,w-40,75);ctx.fillStyle="#fff";ctx.font="bold 31px sans-serif";ctx.fillText(scene.title,40,h-99,w-80);}
  if(scene.ticker){ctx.fillStyle="#b52620";ctx.fillRect(0,h-50,w,50);ctx.fillStyle="#fff";ctx.font="24px sans-serif";ctx.fillText(scene.ticker,20,h-17,w-40);}
}

export default function ProductionPanel({ raw, onTracks }) {
  const [draft,setDraft]=useState(defaults),[program,setProgram]=useState(defaults);
  const [screen,setScreen]=useState(null),[clipName,setClipName]=useState(""),[error,setError]=useState("");
  const [micGain,setMicGain]=useState(1),[clipGain,setClipGain]=useState(1),[ready,setReady]=useState(false);
  const studio=useRef(null),cameraEl=useRef(null),screenEl=useRef(null),clipEl=useRef(null),output=useRef(null),preview=useRef(null);
  const screenRef=useRef(null),clipURL=useRef(null),draftRef=useRef(draft),programRef=useRef(program),mounted=useRef(true),starting=useRef(false);
  draftRef.current=draft;programRef.current=program;
  useEffect(()=>{if(cameraEl.current)cameraEl.current.srcObject=raw.video?new MediaStream([raw.video]):null;},[raw.video]);
  useEffect(()=>{if(screenEl.current)screenEl.current.srcObject=screen;},[screen]);
  useEffect(()=>{
    const timer=setInterval(()=>{if(output.current&&preview.current){draw(output.current,programRef.current,cameraEl.current,screenEl.current,clipEl.current);draw(preview.current,draftRef.current,cameraEl.current,screenEl.current,clipEl.current);}},1000/24);
    return ()=>clearInterval(timer);
  },[]);
  useEffect(()=>{
    const current=studio.current;if(!current||!ready)return;
    current.micSource?.disconnect();current.micSource=null;
    if(raw.audio&&raw.audio.readyState==="live"){current.micSource=current.context.createMediaStreamSource(new MediaStream([raw.audio]));current.micSource.connect(current.mic);}
  },[raw.audio,ready]);
  useEffect(()=>{if(studio.current){studio.current.mic.gain.value=micGain;studio.current.clip.gain.value=program.scene==="clip"?clipGain:0;}},[micGain,clipGain,program.scene,ready]);
  useEffect(()=>{mounted.current=true;return ()=>{mounted.current=false;screenRef.current?.getTracks().forEach(t=>t.stop());if(clipURL.current)URL.revokeObjectURL(clipURL.current);studio.current?.video?.stop();studio.current?.destination?.stream.getTracks().forEach(t=>t.stop());studio.current?.context.close().catch(()=>{});};},[]);
  const start = async()=>{
    if(studio.current||starting.current)return;starting.current=true;
    let context,video;
    try{
      if(!output.current.captureStream)throw new Error("Canvas capture is unavailable. Use Chrome or Edge, or the direct device mode.");
      const AudioContextClass=window.AudioContext||window.webkitAudioContext;
      if(!AudioContextClass)throw new Error("Audio mixing is not supported in this browser.");
      context=new AudioContextClass();await context.resume();
      if(!mounted.current){await context.close();return;}
      const destination=context.createMediaStreamDestination(),mic=context.createGain(),clip=context.createGain();
      mic.connect(destination);clip.connect(destination);clip.gain.value=0;
      context.createMediaElementSource(clipEl.current).connect(clip);
      video=output.current.captureStream(24).getVideoTracks()[0];
      studio.current={context,destination,mic,clip,video};setReady(true);setError("");
      onTracks({video,audio:destination.stream.getAudioTracks()[0]});
    }catch(e){video?.stop();context?.close().catch(()=>{});if(mounted.current)setError(e.message);}finally{starting.current=false;}
  };
  const share=async()=>{try{const stream=await navigator.mediaDevices.getDisplayMedia({video:true,audio:false});if(!mounted.current){stream.getTracks().forEach(t=>t.stop());return;}screenRef.current?.getTracks().forEach(t=>t.stop());screenRef.current=stream;setScreen(stream);stream.getVideoTracks()[0].addEventListener("ended",()=>{if(screenRef.current===stream){screenRef.current=null;setScreen(null);setProgram(p=>["screen","pip"].includes(p.scene)?{...p,scene:"slate"}:p);}});setError("");}catch(e){setError(e.message||"Screen sharing cancelled");}};
  const stopShare=()=>{screenRef.current?.getTracks().forEach(t=>t.stop());screenRef.current=null;setScreen(null);setProgram(p=>["screen","pip"].includes(p.scene)?{...p,scene:"slate"}:p);};
  const loadClip=event=>{const f=event.target.files?.[0];if(!f)return;if(programRef.current.scene==="clip"){setError("Take another scene before replacing the on-air clip.");return;}if(clipURL.current)URL.revokeObjectURL(clipURL.current);clipURL.current=URL.createObjectURL(f);clipEl.current.src=clipURL.current;clipEl.current.load();setClipName(f.name);};
  const take=async()=>{if(["screen","pip"].includes(draft.scene)&&!screen){setError("Start screen sharing before taking this scene.");return;}if(draft.scene==="clip"){if(!clipName){setError("Select a prerecorded file first.");return;}try{clipEl.current.currentTime=0;await clipEl.current.play();}catch(e){setError("This file could not be played: "+e.message);return;}}else clipEl.current.pause();setProgram({...draft});setError("");};
  return <section className="space-y-4 border-t border-white/10 pt-4">
    <h3 className="font-display text-xl">Professional production workspace</h3><p className="text-sm text-gray-400">Prepare a scene in Preview, then Take to programme. The programme canvas and mixed audio are what LoNo receives when you start a test or broadcast.</p>
    {!ready&&<button className={btn} onClick={start}>Start production mixer</button>}{ready&&<p className="text-green-300 text-sm">Production mixer ready · 720p / 24 fps</p>}
    {error&&<p role="alert" className="text-red-300 text-sm">{error}</p>}
    <video ref={cameraEl} muted autoPlay playsInline className="hidden"/><video ref={screenEl} muted autoPlay playsInline className="hidden"/><video ref={clipEl} playsInline preload="metadata" className="hidden" onEnded={()=>setProgram(p=>p.scene==="clip"?{...p,scene:"slate"}:p)}/>
    <div className="grid sm:grid-cols-2 gap-2"><div><p className="text-xs text-gray-400 mb-1">Preview</p><canvas ref={preview} width={1280} height={720} className="w-full rounded-lg bg-black"/></div><div><p className="text-xs text-red-300 mb-1">Programme · {choices.find(c=>c[0]===program.scene)?.[1]}</p><canvas ref={output} width={1280} height={720} className="w-full rounded-lg bg-black"/></div></div>
    <div className="flex flex-wrap gap-2"><button type="button" className={btn} disabled={!ready||!!screen} onClick={share}>Share screen</button>{screen&&<button className={btn} onClick={stopShare}>Stop sharing</button>}<label className={btn}>Load prerecorded media<input type="file" accept="video/*,audio/*" disabled={!ready||program.scene==="clip"} onChange={loadClip} className="sr-only"/></label>{clipName&&<span className="text-xs self-center text-gray-400">{clipName}</span>}</div>
    <label className="block">Preview scene<select className={field} value={draft.scene} onChange={e=>setDraft({...draft,scene:e.target.value})}>{choices.map(([k,l])=><option key={k} value={k}>{l}</option>)}</select></label>
    <label className="block">Station logo text<input className={field} maxLength={24} value={draft.logo} onChange={e=>setDraft({...draft,logo:e.target.value})}/></label><label className="block">Lower third title<input className={field} maxLength={90} value={draft.title} onChange={e=>setDraft({...draft,title:e.target.value})}/></label><label className="block">News ticker text<input className={field} maxLength={150} value={draft.ticker} onChange={e=>setDraft({...draft,ticker:e.target.value})}/></label>
    <button disabled={!ready} onClick={take} className="rounded-full bg-[#FF3B30] px-5 py-2 text-sm disabled:opacity-40">Take to programme</button>
    <div className="grid sm:grid-cols-2 gap-3"><label>Microphone gain · {Math.round(micGain*100)}%<input type="range" min="0" max="2" step="0.05" value={micGain} onChange={e=>setMicGain(Number(e.target.value))} className="w-full"/></label><label>Clip audio gain · {Math.round(clipGain*100)}%<input type="range" min="0" max="2" step="0.05" value={clipGain} onChange={e=>setClipGain(Number(e.target.value))} className="w-full"/></label></div>
    <p className="text-xs text-gray-400">Screen audio is not captured. Device microphone mute applies to the mix. Load media you have permission to broadcast; local files are not uploaded by the mixer.</p>
  </section>;
}
