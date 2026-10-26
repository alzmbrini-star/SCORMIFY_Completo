// Shared viewport contract. Also injected into saved assessments on display.
export const assessmentLayout = `
html,body,#app{width:100%!important;height:100%!important;min-height:0!important;margin:0!important;padding:0!important;overflow:hidden!important}
body{display:block!important;position:relative!important}
#__stage{position:absolute!important;inset:0!important;width:100%!important;height:100%!important;min-width:0!important;min-height:0!important;max-width:none!important;max-height:none!important;transform:none!important;margin:0!important}
.assessment{width:100%!important;height:100%!important;min-height:0!important;overflow:hidden!important;display:flex!important;flex-direction:column!important}
.assessment .top{flex:0 0 auto!important;max-height:25%!important;overflow:auto!important;padding:8px 12px!important}
.assessment .categories{display:flex!important;max-height:none!important;overflow:visible!important}
.assessment .shell{flex:1 1 0!important;min-height:0!important;display:grid!important;grid-template-columns:minmax(0,1.6fr) minmax(300px,1fr)!important;gap:10px!important;padding:8px!important;overflow:hidden!important}
.assessment .work,.assessment .panel{height:100%!important;min-height:0!important;overflow:hidden!important;display:flex!important;flex-direction:column!important}
.assessment .stage{flex:1 1 0!important;min-height:0!important;overflow:auto!important;padding:10px!important}
.assessment .panel-body{flex:1 1 0!important;min-height:0!important;overflow:auto!important;padding:16px!important;overscroll-behavior:contain}
.assessment .footer{flex:0 0 auto!important;position:relative!important;padding:10px 14px!important;z-index:2}
.assessment .media-head{flex:0 0 38px!important}
.assessment .panel h1{font-size:clamp(18px,2vw,26px)}
/* Keep exported questions readable at their actual iframe viewport size. */
.assessment{font-family:Arial,Helvetica,sans-serif;line-height:1.45}
.assessment button{font-family:inherit;line-height:1.4}
.assessment .panel h1{font-size:clamp(22px,2vw,32px);line-height:1.2}
.assessment .panel .prompt{font-size:clamp(17px,1.35vw,23px);line-height:1.45;font-weight:600}
.assessment .option,.assessment .card,.assessment .feedback{font-size:clamp(16px,1.2vw,21px);line-height:1.45;font-weight:600;overflow-wrap:anywhere}
.assessment .instructions,.assessment .zone .hint{font-size:clamp(14px,1vw,18px);color:#dce6ff;line-height:1.5}
.assessment .cat,.assessment .eyebrow,.assessment .badge,.assessment .tag{font-size:clamp(12px,.85vw,16px);line-height:1.4}
.assessment .media-head,.assessment .footer button,.assessment .top>span,.assessment .top>.skip{font-size:clamp(14px,1.05vw,19px)}
.assessment .num{font-size:15px;width:32px;height:32px}
.assessment .tray{display:grid;grid-template-columns:1fr;gap:10px;padding:12px 0;align-content:start}
.assessment .card{margin:0;padding:12px;text-align:left;white-space:normal}
.assessment .zone .card{margin-top:10px}
.assessment .option{white-space:normal;padding:12px}
.assessment .order .option{min-width:0}
.assessment .media-head{gap:8px;padding:0 10px}.media-head>span:first-child{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}
.image-expand,.image-close{border:1px solid #b8caff66;border-radius:8px;padding:7px 12px;background:#203678;color:white;cursor:pointer;white-space:nowrap}
.visual-choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;width:100%;margin:auto;align-content:start}
.assessment .visual-choice{position:relative;display:flex;flex-direction:column;gap:8px;background:#f5f7fb;color:#142344;padding:12px;border:3px solid transparent;min-width:0;text-align:center;justify-content:center;align-self:stretch}
.assessment .visual-choice .card-image{width:100%!important;height:clamp(110px,20vh,240px)!important;max-height:none!important;object-fit:contain;margin:10px 0 0;border-radius:9px}
.visual-caption{font-size:clamp(13px,1.3vw,20px);font-weight:800;overflow-wrap:anywhere}.visual-marker{font-size:11px;border-radius:20px;padding:3px 7px;background:#142344;color:white}
.assessment .visual-choice.selected{border-color:#ffd057;background:#fff6d8;box-shadow:0 0 0 2px #ffd05755}.assessment .visual-choice.answer-correct{border-color:#37dba0;background:#e3fff1}.assessment .visual-choice.answer-incorrect{border-color:#ff6576;background:#ffe8ec}.assessment .visual-choice:disabled{opacity:1}.visual-choice:focus-visible,.image-expand:focus-visible{outline:3px solid #ffd057;outline-offset:2px}
.image-overlay{position:fixed;inset:0;z-index:1000;background:#03091cf2;display:flex;align-items:center;justify-content:center;padding:60px 20px 20px}.image-overlay>img{max-width:100%;max-height:100%;object-fit:contain}.image-close{position:absolute;top:12px;right:14px}
.assessment .stage.has-support{display:flex;flex-direction:column;align-items:stretch;gap:12px}.assessment .stage.has-support .assessment-support{flex:0 0 auto;height:38%;min-height:100px;margin:0;overflow:auto}.assessment .stage.has-support .assessment-support img,.assessment .stage.has-support .assessment-support video,.assessment .stage.has-support .assessment-support iframe{width:100%;height:100%;max-height:100%;object-fit:contain}.assessment .stage.has-support .dropzones{flex:1 0 auto;height:auto;min-height:180px}
@media(max-width:650px){.assessment .shell{grid-template-columns:1fr!important;grid-template-rows:minmax(90px,32%) minmax(0,1fr)!important}.assessment .panel-body{padding:10px!important}.assessment .panel h1{margin:8px 0}.assessment .footer{padding:8px!important}.assessment .top{max-height:22%!important}}
`;
