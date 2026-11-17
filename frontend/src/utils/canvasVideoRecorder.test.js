import {recordCanvasAttempt, recordCanvasVideo, videoMimeCandidates} from './canvasVideoRecorder';

let tracks, instances;
class Recorder {
  static isTypeSupported(type) { return type.startsWith('video/webm'); }
  constructor(stream, options) { this.stream=stream; this.mimeType=options.mimeType || 'video/webm'; this.state='inactive'; instances.push(this); }
  start() { this.state='recording'; this.onstart(); }
  requestData() { this.ondataavailable({data:new Blob(['frame'],{type:this.mimeType})}); }
  stop() { this.state='inactive'; this.onstop(); }
}
function options(extra={}) {
  const track={readyState:'live',stop:jest.fn(),requestFrame:jest.fn()}; tracks.push(track);
  return {canvas:{captureStream:jest.fn(()=>({getVideoTracks:()=>[track],getTracks:()=>[track]}))},
    duration:.1,draw:jest.fn(),start:jest.fn(),stop:jest.fn(),Recorder,...extra};
}
beforeEach(()=>{jest.useFakeTimers(); tracks=[]; instances=[]; global.MediaStream=class {constructor(list){this.tracks=list}};});
afterEach(()=>jest.useRealTimers());
test('silent export has no empty audio track, requests frames, and finalizes data',async()=>{
  const config=options(); const pending=recordCanvasAttempt({...config,mimeType:'video/webm'});
  jest.advanceTimersByTime(200);
  const blob=await pending; expect(blob.size).toBeGreaterThan(0);
  expect(instances[0].stream.tracks).toHaveLength(1);
  expect(config.start).toHaveBeenCalledTimes(1);expect(config.stop).toHaveBeenCalledTimes(1);
  expect(tracks[0].requestFrame).toHaveBeenCalled();expect(tracks[0].stop).toHaveBeenCalled();
  expect(jest.getTimerCount()).toBe(0);
});
test('narration track is retained when supplied',async()=>{
  const sound={kind:'audio'}, config=options({audioTracks:[sound]});
  const pending=recordCanvasAttempt({...config,mimeType:'video/webm'});jest.advanceTimersByTime(200);await pending;
  expect(instances[0].stream.tracks[1]).toBe(sound);
});
test('unexpected stop is not reported as complete',async()=>{
  const config=options({duration:60});const pending=recordCanvasAttempt(config);const assertion=expect(pending).rejects.toThrow('antes de gerar');
  instances[0].requestData();instances[0].stop();await assertion;
  expect(tracks[0].stop).toHaveBeenCalled();expect(jest.getTimerCount()).toBe(0);
});
test('codec failure retries and all attempt resources are released',async()=>{
  class Retry extends Recorder {constructor(stream,options){super(stream,options);if(options.mimeType.includes('vp8'))throw new Error('codec indisponível');}}
  const retry=jest.fn(), pending=recordCanvasVideo(options({Recorder:Retry,onRetry:retry}));
  await Promise.resolve();jest.advanceTimersByTime(200);expect((await pending).size).toBeGreaterThan(0);
  expect(retry).toHaveBeenCalledTimes(1);tracks.forEach(t=>expect(t.stop).toHaveBeenCalled());
});
test('a stalled encoder times out and does not leave timers or tracks',async()=>{
  class Stalled extends Recorder {requestData(){}}
  const config=options({Recorder:Stalled,duration:60,firstDataTimeout:1000});
  const pending=recordCanvasAttempt(config);const assertion=expect(pending).rejects.toThrow('não produziu dados');
  jest.advanceTimersByTime(1100);await assertion;expect(tracks[0].stop).toHaveBeenCalled();expect(jest.getTimerCount()).toBe(0);
});
test('VP8 precedes VP9, plus browser-selected fallback',()=>{
  const types=videoMimeCandidates(Recorder);expect(types[0]).toContain('vp8');expect(types.at(-1)).toBe('');
});
