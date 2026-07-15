import time, json, traceback
from pathlib import Path
from DrissionPage import Chromium, ChromiumOptions
from grok_register_ttk import create_browser_options, load_config

load_config() if False else None
# load config manually
import grok_register_ttk as reg
reg.load_config() if hasattr(reg, 'load_config') else None

opts = create_browser_options()
# keep visible
browser = Chromium(opts)
page = browser.latest_tab
out = Path('debug_signup')
out.mkdir(exist_ok=True)
try:
    page.get('https://accounts.x.ai/sign-up?redirect=grok-com')
    time.sleep(3)
    html1 = page.html or ''
    (out/'step1.html').write_text(html1, encoding='utf-8')
    try:
        page.get_screenshot(path=str(out/'step1.png'), full_page=True)
    except Exception as e:
        print('shot1', e)
    print('URL1', page.url)
    print('title1', page.title)
    print('len1', len(html1))
    # click email signup like script
    clicked = page.run_js(r"""
const nodes = Array.from(document.querySelectorAll('button, a, [role="button"], div[role="button"]'));
const target = nodes.find((node) => {
  const t = (node.innerText || node.textContent || '').replace(/\s+/g, '');
  return t.includes('使用邮箱注册') || t.toLowerCase().includes('signupwithemail') || t.toLowerCase().includes('continuewithemail') || t.includes('邮箱');
});
if (target) { target.click(); return (target.innerText||'').slice(0,80); }
return null;
""")
    print('clicked', clicked)
    time.sleep(5)
    html2 = page.html or ''
    (out/'step2.html').write_text(html2, encoding='utf-8')
    try:
        page.get_screenshot(path=str(out/'step2.png'), full_page=True)
    except Exception as e:
        print('shot2', e)
    print('URL2', page.url)
    print('title2', page.title)
    print('len2', len(html2))
    info = page.run_js(r"""
const inputs = Array.from(document.querySelectorAll('input')).map(i => ({
  type:i.type, name:i.name, id:i.id, test:i.getAttribute('data-testid'), placeholder:i.placeholder,
  visible: !!(i.offsetWidth||i.offsetHeight), disabled:i.disabled
}));
const texts = Array.from(document.querySelectorAll('button,a,[role="button"]')).slice(0,30).map(n => (n.innerText||n.textContent||'').replace(/\s+/g,' ').trim()).filter(Boolean);
const bodyText = (document.body && document.body.innerText || '').slice(0,1500);
return {inputs, texts, bodyText, hasTurnstile: !!document.querySelector('iframe[src*="turnstile"], [data-sitekey], .cf-turnstile')};
""")
    print(json.dumps(info, ensure_ascii=False, indent=2)[:4000])
except Exception:
    traceback.print_exc()
finally:
    try:
        browser.quit()
    except Exception:
        pass
