"""Offline render regressions: real glyph tracing, progressive fills, custom shapes."""
import math
from PIL import Image
from services import whiteboard_plan_renderer as renderer
from services.whiteboard_renderer import _resolve_font_path
from services.whiteboard_ai_plan import prepare_render_plan, _normalize_plan
from services.whiteboard_shapes import path_for_op


def test_plan_text_uses_normal_glyph_paths_and_vertical_pen_motion():
    spec=renderer._prepare_op({'type':'text','text':'Olá','x':180,'y':180,'font_size':90},_resolve_font_path('caveat'),3)
    canvas=Image.new('RGBA',(1920,1080))
    tips=[]
    for step in range(spec['substeps']):
        frame=canvas.copy()
        tip=renderer._draw_plan_text(frame,spec,(step+1)/spec['frames'])
        tips.append(tip)
        entry=spec['cache']['O'];x,y=entry['pen_positions'][step]
        assert tip==(180+entry['left']+x,180+entry['top']+y)
        frame.close()
    assert max(p[1] for p in tips)-min(p[1] for p in tips)>20
    assert max(p[0] for p in tips)-min(p[0] for p in tips)>15
    renderer._commit_op(canvas,spec)
    assert canvas.getbbox() and 'cache' not in spec
    canvas.close()


def test_plan_text_transparency_space_accents_and_replay():
    spec=renderer._prepare_op({'type':'text','text':'ação é útil','x':200,'y':180,'font_size':64,'color':'#2563eb'},_resolve_font_path('caveat'))
    canvas=Image.new('RGBA',(1920,1080));hand=Image.new('RGBA',(1,1))
    frames=[renderer._compose_frame(canvas,spec,p,hand,0,0) for p in (0,.4,1,.2)]
    assert all(frame.getpixel((0,0))[3]==0 for frame in frames)
    assert frames[2].getbbox()[2]>frames[1].getbbox()[2]
    renderer._commit_op(canvas,spec)
    for frame in frames:frame.close()
    canvas.close();hand.close()


def test_fill_is_progressive_and_never_paints_over_previous_text():
    spec=renderer._prepare_op({'type':'rectangle','x':150,'y':150,'w':300,'h':150,'color':'#111111','fill':'#2563eb','fill_opacity':100},_resolve_font_path('caveat'))
    canvas=Image.new('RGBA',(1920,1080));canvas.putpixel((250,220),(0,0,0,255));hand=Image.new('RGBA',(1,1))
    before=renderer._compose_frame(canvas,spec,.65,hand,0,0)
    during=renderer._compose_frame(canvas,spec,.85,hand,0,0)
    after=renderer._compose_frame(canvas,spec,1,hand,0,0)
    assert before.getpixel((200,190))[3]==0
    assert during.getpixel((200,170))==(37,99,235,255)
    assert during.getpixel((200,280))[3]==0
    assert after.getpixel((200,280))==(37,99,235,255)
    assert after.getpixel((250,220))==(0,0,0,255)
    assert after.getpixel((0,0))[3]==0
    renderer._commit_op(canvas,spec)
    assert canvas.getpixel((200,280))==after.getpixel((200,280))
    for image in (before,during,after,canvas,hand):image.close()


def test_custom_geometry_is_bounded_and_fills_survive_preparation():
    plan=prepare_render_plan({'ops':[{'id':'roof','type':'polygon','points':[[-20,200],[400,200],[300,400]],'color':'blue','fill':'red','fill_opacity':200},
        {'id':'wire','type':'polyline','points':[[200,600],[300,520],[400,600]],'fill':'red'}]})
    polygon,line=plan['ops']
    assert polygon['points'][0][0]==0 and polygon['fill_opacity']==100
    assert 'fill' not in line
    assert path_for_op(polygon)[0]==path_for_op(polygon)[-1]
    assert path_for_op(line)[0]!=path_for_op(line)[-1]
    assert len(_normalize_plan({'ops':[{'type':'polygon','points':[[1,2]]}]},base_color=None,allow_color_per_shape=True)['ops'])==0


def test_only_closed_icon_regions_are_filled_and_catalog_is_real():
    spec=renderer._prepare_op({'type':'icon','name':'heart','x':500,'y':500,'size':250,'fill':'#ef4444'},_resolve_font_path('caveat'))
    assert renderer._fill_paths(spec)
    assert not renderer._fill_paths({'kind':'icon','fill':'red','strokes':[[(0,0),(4,0),(4,4),(0,4)]]})
    assert math.dist(spec['strokes'][0][0],spec['strokes'][0][-1])<.1
