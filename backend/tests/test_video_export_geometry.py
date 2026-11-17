import copy
from services.video_export_geometry import video_slide_dimensions

def test_slide_overrides_and_course_inheritance_do_not_mutate_source():
    slide={'title':'Original','width':None,'height':None,'elements':[{'src':'image.png'}]}
    course={'width':1920,'height':820};before=copy.deepcopy(slide)
    assert video_slide_dimensions(slide,course)==(1920,820)
    assert video_slide_dimensions({'width':600,'height':900},course)==(600,900)
    assert slide==before

def test_invalid_dimensions_have_finite_positive_defaults():
    assert video_slide_dimensions({'width':0,'height':'bad'},{'width':float('inf'),'height':None})==(1920,820)
    assert video_slide_dimensions({'width':'960','height':'540'}, {})==(960,540)
