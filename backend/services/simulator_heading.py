"""Reconcile an editorial heading without changing a generated simulation."""
import html
import re
from html.parser import HTMLParser


class _Headings(HTMLParser):
    def __init__(self,source):
        super().__init__(convert_charrefs=True)
        self.source=source
        self.offsets=[0]
        for match in re.finditer('\n',source):self.offsets.append(match.end())
        self.blocked=0
        self.current=None
        self.headings=[]

    def source_position(self):
        line,column=self.getpos()
        return self.offsets[line-1]+column

    def handle_starttag(self,tag,attrs):
        if tag in ('script','style','template','noscript'):
            if self.current:self.current['safe']=False
            self.blocked+=1
        if self.blocked:return
        attributes=dict(attrs)
        if tag in ('h1','h2') and self.current is None:
            if 'hidden' in attributes or attributes.get('aria-hidden')=='true' or re.search(r'display\s*:\s*none|visibility\s*:\s*hidden',attributes.get('style',''),re.I):return
            self.current={'tag':tag,'start':self.source_position()+len(self.get_starttag_text()),'safe':True}
        elif self.current:
            # Preserve IDs/listeners/interactive child nodes. Simple emphasis
            # is editorial text; replacing that content does not remove state.
            if tag not in ('span','strong','b','em','i','br') or any(k in ('id','name') or k.startswith('on') or k.startswith('data-') for k,v in attrs):
                self.current['safe']=False

    def handle_endtag(self,tag):
        if tag in ('script','style','template','noscript'):
            self.blocked=max(0,self.blocked-1)
            return
        if not self.blocked and self.current and self.current['tag']==tag:
            self.current['end']=self.source_position()
            self.headings.append(self.current)
            self.current=None


def reconcile_heading(source,title):
    """Canonical title is server-owned copy, not an AI functionality gate.

    Only an existing safe heading is changed; its attributes, geometry and all
    other markup/scripts remain intact. Never add a floating/overlapping title.
    """
    parser=_Headings(source)
    parser.feed(source)
    parser.close()
    candidates=[h for h in parser.headings if h['safe']]
    heading=next((h for h in candidates if h['tag']=='h1'),None) or next(iter(candidates),None)
    if not heading:return source
    return source[:heading['start']]+html.escape(title,quote=False)+source[heading['end']:]
