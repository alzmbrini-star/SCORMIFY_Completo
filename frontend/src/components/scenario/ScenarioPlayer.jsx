import React, {useEffect, useRef} from 'react';
import '../../utils/scenarioPresentation';
import {getApiUrl} from '../../utils/apiUrl';

export default function ScenarioPlayer({scenarioData,onComplete}) {
  const host=useRef(null),complete=useRef(onComplete);complete.current=onComplete;
  useEffect(()=>{
    if(!host.current||!scenarioData)return;
    const player=window.ScormifyScenario.mount(host.current,scenarioData,{
      onComplete:result=>complete.current?.(result),
      resolveImage:url=>url.startsWith('/api/')?getApiUrl()+url:url
    });
    return ()=>player.destroy();
  },[scenarioData]);
  return <div ref={host} className="w-full h-full" data-testid="scenario-player" />;
}
