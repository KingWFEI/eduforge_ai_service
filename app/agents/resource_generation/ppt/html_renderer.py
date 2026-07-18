from __future__ import annotations

from app.agents.resource_generation.ppt.html_sanitizer import HtmlSanitizer
from app.agents.resource_generation.ppt.schemas import PptDeck, StyleSelection


class PptHtmlRenderer:
    CSP = (
        "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
        "img-src data:; font-src data:; connect-src 'none'; frame-src 'none'; "
        "object-src 'none'; base-uri 'none'; form-action 'none'"
    )

    def render(self, deck: PptDeck, style: StyleSelection) -> str:
        slides = "\n".join(self._render_slide(slide, len(deck.slides)) for slide in deck.slides)
        document = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{self.CSP}">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>{HtmlSanitizer.escape(deck.slides[0].title)}</title>
<style>
*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#0b1220;font-family:Arial,"Microsoft YaHei",sans-serif}}
#viewport{{position:fixed;inset:0;overflow:hidden}}#stage{{position:absolute;width:1920px;height:1080px;transform-origin:top left;background:#f7f3e8;color:#102a43;overflow:hidden}}
.slide{{position:absolute;inset:0;width:1920px;height:1080px;padding:104px 120px 88px;display:none;overflow:hidden;background:#f7f3e8}}
.slide.active,.slide.visible{{display:flex;flex-direction:column}}.slide::before{{content:"";position:absolute;left:0;top:0;width:24px;height:100%;background:#175cd3}}
h1{{font-size:70px;line-height:1.12;margin:0 0 22px;color:#0b3b8f;max-width:1500px}}h2{{font-size:30px;font-weight:400;margin:0 0 46px;color:#486581}}
.goal{{font-size:23px;color:#486581;margin-bottom:28px}}.blocks{{display:grid;gap:22px;max-width:1580px;min-height:0}}.block{{padding:24px 30px;border:2px solid #b9c8dc;border-radius:20px;background:#fff;font-size:30px;line-height:1.45;overflow:hidden}}
.block ul{{margin:0;padding-left:34px}}pre{{white-space:pre-wrap;font-size:23px;line-height:1.35}}img{{max-width:100%;max-height:100%;object-fit:contain;object-position:center}}
.footer{{position:absolute;left:120px;right:90px;bottom:34px;display:flex;justify-content:space-between;font-size:19px;color:#627d98}}.progress{{height:7px;background:#d9e2ec;border-radius:9px;overflow:hidden;width:360px}}.progress span{{display:block;height:100%;background:#175cd3}}
@media(prefers-reduced-motion:reduce){{*{{animation:none!important;transition:none!important}}}}
</style></head><body><div id="viewport"><main id="stage" data-style="{HtmlSanitizer.escape(style.style_id)}">{slides}</main></div>
<script>
(()=>{{'use strict';const stage=document.getElementById('stage'),slides=[...document.querySelectorAll('.slide')];let current=0,touchX=null,lastWheel=0;
function scale(){{const s=Math.min(innerWidth/1920,innerHeight/1080),x=(innerWidth-1920*s)/2,y=(innerHeight-1080*s)/2;stage.style.transform=`translate(${{x}}px,${{y}}px) scale(${{s}})`}}
function show(n){{current=(n+slides.length)%slides.length;slides.forEach((el,i)=>{{el.classList.toggle('active',i===current);el.classList.toggle('visible',i===current)}})}}
addEventListener('resize',scale);addEventListener('keydown',e=>{{if(['ArrowRight','ArrowDown',' '].includes(e.key))show(current+1);if(['ArrowLeft','ArrowUp'].includes(e.key))show(current-1)}});
addEventListener('wheel',e=>{{const now=Date.now();if(now-lastWheel<450)return;lastWheel=now;show(current+(e.deltaY>0?1:-1))}},{{passive:true}});
addEventListener('touchstart',e=>touchX=e.changedTouches[0].clientX,{{passive:true}});addEventListener('touchend',e=>{{if(touchX===null)return;const d=e.changedTouches[0].clientX-touchX;if(Math.abs(d)>45)show(current+(d<0?1:-1));touchX=null}},{{passive:true}});scale();show(0)}})();
</script></body></html>'''
        HtmlSanitizer.assert_safe_document(document)
        return document

    def _render_slide(self, slide, total: int) -> str:
        blocks = "".join(self._render_block(block) for block in slide.content_blocks)
        sources = "、".join(HtmlSanitizer.escape(item) for item in slide.source_chunk_ids) or "课程结构"
        return f'''<section class="slide{' active visible' if slide.slide_no == 1 else ''}" data-slide-no="{slide.slide_no}">
<h1>{HtmlSanitizer.escape(slide.title)}</h1><h2>{HtmlSanitizer.escape(slide.subtitle)}</h2>
<div class="goal">学习目标：{HtmlSanitizer.escape(slide.learning_goal)}</div><div class="blocks">{blocks}</div>
<div class="footer"><span>来源：{sources}</span><span>{slide.slide_no}/{total}</span><div class="progress"><span style="width:{slide.slide_no / total * 100:.2f}%"></span></div></div></section>'''

    def _render_block(self, block) -> str:
        title = f"<strong>{HtmlSanitizer.escape(block.title)}</strong>" if block.title else ""
        if block.items:
            body = "<ul>" + "".join(f"<li>{HtmlSanitizer.escape(item)}</li>" for item in block.items) + "</ul>"
        elif block.type == "code":
            body = f"<pre><code>{HtmlSanitizer.escape(block.text)}</code></pre>"
        else:
            body = f"<p>{HtmlSanitizer.escape(block.text)}</p>"
        return f'<div class="block block-{HtmlSanitizer.escape(block.type)}">{title}{body}</div>'
