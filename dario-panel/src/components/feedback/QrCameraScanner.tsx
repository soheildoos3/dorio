import {Camera, CameraOff, ImageUp, ScanLine} from 'lucide-react';
import {useEffect, useRef, useState} from 'react';
import {inventoryApi} from '../../api/inventory';
import {ApiError} from '../../lib/api';
import {Button} from '../ui/Button';

type Detection={rawValue:string};
type Detector={detect:(source:unknown)=>Promise<Detection[]>};
type DetectorCtor=new(options?:{formats?:string[]})=>Detector;

type Props={onDetected:(value:string)=>void; disabled?:boolean};

async function videoFrameFile(video:HTMLVideoElement):Promise<File|null>{
  if(!video.videoWidth||!video.videoHeight)return null;
  const maxWidth=1280;
  const scale=Math.min(1,maxWidth/video.videoWidth);
  const canvas=document.createElement('canvas');
  canvas.width=Math.max(1,Math.round(video.videoWidth*scale));
  canvas.height=Math.max(1,Math.round(video.videoHeight*scale));
  const ctx=canvas.getContext('2d',{willReadFrequently:false});
  if(!ctx)return null;
  ctx.drawImage(video,0,0,canvas.width,canvas.height);
  const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/jpeg',0.82));
  return blob?new File([blob],'qr-frame.jpg',{type:'image/jpeg'}):null;
}

export function QrCameraScanner({onDetected,disabled}:Props){
  const videoRef=useRef<HTMLVideoElement|null>(null);
  const captureRef=useRef<HTMLInputElement|null>(null);
  const fileRef=useRef<HTMLInputElement|null>(null);
  const streamRef=useRef<MediaStream|null>(null);
  const frameRef=useRef<number|null>(null);
  const runningRef=useRef(false);
  const [active,setActive]=useState(false);
  const [decoding,setDecoding]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [mode,setMode]=useState<'native'|'server'|null>(null);

  function stop(){
    runningRef.current=false;
    if(frameRef.current!==null)cancelAnimationFrame(frameRef.current);
    frameRef.current=null;
    streamRef.current?.getTracks().forEach(t=>t.stop());
    streamRef.current=null;
    if(videoRef.current)videoRef.current.srcObject=null;
    setActive(false);
    setMode(null);
  }

  async function decodeFile(file:File){
    setError(null);
    setDecoding(true);
    try{
      const result=await inventoryApi.decodeQrImage(file);
      const value=result.value?.trim();
      if(!value)throw new Error('QR از تصویر خوانده نشد');
      onDetected(value);
      stop();
    }catch(err){
      setError(err instanceof Error?err.message:'خواندن QR از تصویر ناموفق بود.');
    }finally{
      setDecoding(false);
    }
  }

  async function start(){
    setError(null);

    // Mobile browsers block live camera APIs on plain HTTP (except localhost).
    // In that case open the phone camera through a capture input and decode the
    // resulting photo on the backend instead.
    if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia){
      setError('اسکن زنده روی HTTP شبکه محلی توسط مرورگر مسدود است؛ دوربین گوشی برای گرفتن عکس QR باز می‌شود.');
      captureRef.current?.click();
      return;
    }

    try{
      const stream=await navigator.mediaDevices.getUserMedia({
        video:{facingMode:{ideal:'environment'},width:{ideal:1920},height:{ideal:1080}},
        audio:false,
      });
      streamRef.current=stream;
      const video=videoRef.current;
      if(!video)throw new Error('نمای دوربین آماده نیست');
      video.srcObject=stream;
      await video.play();
      setActive(true);
      runningRef.current=true;

      const DetectorClass=(window as unknown as {BarcodeDetector?:DetectorCtor}).BarcodeDetector;
      const detector=DetectorClass?new DetectorClass({formats:['qr_code']}):null;
      setMode(detector?'native':'server');

      let busy=false;
      let lastServerAttempt=0;
      const loop=async(now:number)=>{
        if(!runningRef.current)return;
        if(!busy&&video.readyState>=2){
          const shouldTry=!!detector||(now-lastServerAttempt>=900);
          if(shouldTry){
            busy=true;
            try{
              let value:string|undefined;
              if(detector){
                const found=await detector.detect(video);
                value=found.find(x=>x.rawValue?.trim())?.rawValue?.trim();
              }else{
                lastServerAttempt=now;
                const frame=await videoFrameFile(video);
                if(frame){
                  try{
                    value=(await inventoryApi.decodeQrImage(frame)).value?.trim();
                  }catch(err){
                    // 422 means this frame simply had no readable QR; keep scanning.
                    if(!(err instanceof ApiError&&err.status===422))throw err;
                  }
                }
              }
              if(value){
                onDetected(value);
                stop();
                return;
              }
            }catch(err){
              // Native BarcodeDetector can fail on transient frames; only surface
              // backend/configuration errors from the fallback scanner.
              if(!detector){
                setError(err instanceof Error?err.message:'خواندن QR ناموفق بود.');
                stop();
                return;
              }
            }finally{busy=false;}
          }
        }
        frameRef.current=requestAnimationFrame(loop);
      };
      frameRef.current=requestAnimationFrame(loop);
    }catch(err){
      stop();
      const name=err instanceof DOMException?err.name:'';
      if(name==='NotAllowedError'){
        setError('اجازه دوربین داده نشد. دسترسی Camera را برای این سایت فعال کنید یا از «گرفتن عکس QR» استفاده کنید.');
      }else if(name==='NotFoundError'){
        setError('دوربین روی این دستگاه پیدا نشد؛ می‌توانید عکس QR را انتخاب کنید.');
      }else{
        setError(err instanceof Error?err.message:'بازکردن دوربین ناموفق بود.');
      }
    }
  }

  useEffect(()=>()=>stop(),[]);

  return <div className="space-y-3">
    <input
      ref={captureRef}
      type="file"
      accept="image/*"
      capture="environment"
      className="hidden"
      onChange={e=>{const file=e.target.files?.[0];e.currentTarget.value='';if(file)void decodeFile(file)}}
    />
    <input
      ref={fileRef}
      type="file"
      accept="image/*"
      className="hidden"
      onChange={e=>{const file=e.target.files?.[0];e.currentTarget.value='';if(file)void decodeFile(file)}}
    />

    <div className={`relative overflow-hidden rounded-2xl border bg-slate-950 ${active?'block':'hidden'}`}>
      <video ref={videoRef} playsInline muted autoPlay className="aspect-[4/3] w-full object-cover"/>
      <div className="pointer-events-none absolute inset-0 grid place-items-center"><div className="h-44 w-44 rounded-3xl border-2 border-white/80 shadow-[0_0_0_999px_rgba(2,6,23,.28)]"><ScanLine className="m-auto mt-20 h-6 w-6 text-white/80"/></div></div>
      <div className="absolute bottom-3 inset-x-3 rounded-xl bg-black/55 px-3 py-2 text-center text-xs text-white">
        QR محصول را داخل کادر نگه دارید؛ {mode==='server'?'خواندن تصویر با موتور QR سرور انجام می‌شود.':'پس از خواندن، دوربین خودکار بسته می‌شود.'}
      </div>
    </div>

    <div className="flex flex-wrap gap-2">
      {!active?<Button type="button" variant="secondary" disabled={disabled||decoding} onClick={()=>void start()}><Camera className="h-4 w-4"/>اسکن با دوربین</Button>:<Button type="button" variant="secondary" onClick={stop}><CameraOff className="h-4 w-4"/>بستن دوربین</Button>}
      {!active&&<Button type="button" variant="ghost" disabled={disabled||decoding} onClick={()=>captureRef.current?.click()}><Camera className="h-4 w-4"/>{decoding?'در حال خواندن…':'گرفتن عکس QR'}</Button>}
      {!active&&<Button type="button" variant="ghost" disabled={disabled||decoding} onClick={()=>fileRef.current?.click()}><ImageUp className="h-4 w-4"/>انتخاب عکس QR</Button>}
    </div>

    {!window.isSecureContext&&<p className="rounded-xl bg-sky-50 px-3 py-2 text-xs leading-6 text-sky-800">این صفحه با HTTP باز شده است؛ اسکن زنده مرورگر ممکن نیست. دکمه «اسکن با دوربین» به‌صورت خودکار از دوربین عکس می‌گیرد و QR را روی سرور می‌خواند.</p>}
    {error&&<p className="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-6 text-amber-800">{error}</p>}
  </div>;
}
