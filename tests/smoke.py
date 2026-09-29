# Loads each app version in headless Chromium (network blocked here) and records JS errors at startup.
import sys, asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for v in sys.argv[1:]:
            pg = await b.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
            pg.on("console", lambda m: errs.append(f"console.{m.type}: {m.text[:120]}") if m.type == "error" else None)
            await pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
            await pg.goto(f"file:///home/claude/work/cinemeter-{v}.html")
            await pg.wait_for_timeout(2500)
            fns = await pg.evaluate("['openDetail','goHome','setFilter','sendChat','rerollHero','loadMoreMovies'].map(n => typeof window[n])")
            grid = await pg.evaluate("document.getElementById('movieGrid').innerText.slice(0,120)")
            print(v, "| window fns:", fns, "| grid:", grid.replace("\n"," "), "| pageerrors:", [e for e in errs if e.startswith("pageerror")])
            await pg.screenshot(path=f"/home/claude/work/tests/results/smoke-{v}.png")
        await b.close()
asyncio.run(main())
