import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

// A bounded menu of dialog-opening actions, not generated JS or DOM clicking.
// It never confirms a dialog, saves a project, generates AI content or exports.
export default function useCreatorHelpNavigation(actions, ready = true) {
  const location=useLocation(),navigate=useNavigate(),latest=useRef(actions);
  latest.current=actions;
  useEffect(()=>{
    if(!ready)return;
    const params=new URLSearchParams(location.search),action=params.get('help');
    if(!action||!Object.prototype.hasOwnProperty.call(latest.current,action)||typeof latest.current[action]!=='function')return;
    params.delete('help');
    navigate({pathname:location.pathname,search:params.toString()?`?${params}`:'',hash:location.hash},{replace:true});
    latest.current[action]();
  },[location.pathname,location.search,location.hash,location.key,navigate,ready]);
}
