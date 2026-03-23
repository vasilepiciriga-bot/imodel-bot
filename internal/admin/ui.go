package admin

import (
	"strconv"

	"github.com/gofiber/fiber/v2"
	"imodel-bot/internal/config"
	"imodel-bot/internal/repo"
)

// RegisterAdminUI wires lightweight admin HTML and JSON endpoints.
func RegisterAdminUI(app *fiber.App, cfg config.Config, store *repo.Store) {
	// GET /admin/user?uid=...
	app.Get("/admin/user", func(c *fiber.Ctx) error {
		if c.Get("X-Admin-Secret") != cfg.AdminSecret || cfg.AdminSecret == "" {
			return c.SendStatus(fiber.StatusUnauthorized)
		}
		s := c.Query("uid")
		if s == "" {
			return c.Status(400).JSON(fiber.Map{"error": "uid required"})
		}
		u64, err := strconv.ParseInt(s, 10, 64)
		if err != nil {
			return c.Status(400).JSON(fiber.Map{"error": "bad uid"})
		}
		info, err := store.GetUserInfo(c.Context(), u64)
		if err != nil {
			return c.Status(404).JSON(fiber.Map{"error": "not found"})
		}
		return c.JSON(info)
	})

	// Minimal HTML admin page (client-side calls with X-Admin-Secret from localStorage)
	app.Get("/admin/ui", func(c *fiber.Ctx) error {
		html := adminHTML()
		return c.Type("html").SendString(html)
	})
}

func adminHTML() string {
	return `<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>iModel Admin</title>
<style>body{font:14px/1.5 system-ui;margin:20px}input,button{font:inherit;padding:6px 10px;margin:4px 0}section{border:1px solid #eee;border-radius:8px;padding:12px;margin:10px 0}code{background:#f6f6f6;padding:2px 4px;border-radius:4px}</style>
</head><body>
<h2>iModel Admin</h2>
<section>
<label>Admin Secret <input id="sec" type="password" placeholder="X-Admin-Secret"/></label>
<button onclick="save()">Save</button>
<span id="saved" style="color:green"></span>
</section>
<section>
<h3>Grant Credits</h3>
<input id="uid" placeholder="User ID"/>
<input id="n" placeholder="Credits" value="10"/>
<button onclick="grant()">Grant</button>
<pre id="grant_out"></pre>
</section>
<section>
<h3>Whitelist</h3>
<input id="wuid" placeholder="User ID"/>
<button onclick="wset(true)">Add</button>
<button onclick="wset(false)">Remove</button>
<pre id="wl_out"></pre>
</section>
<section>
<h3>Lookup User</h3>
<input id="luid" placeholder="User ID"/>
<button onclick="lookup()">Lookup</button>
<pre id="look_out"></pre>
</section>
<section>
<h3>Whitelist List</h3>
<button onclick="loadwl()">Refresh</button>
<pre id="list_out"></pre>
</section>
<script>
const H = ()=>({ 'Content-Type':'application/json', 'X-Admin-Secret': localStorage.getItem('admsec')||'' });
function save(){ localStorage.setItem('admsec', document.getElementById('sec').value); document.getElementById('saved').textContent='Saved'; setTimeout(()=>document.getElementById('saved').textContent='',1000); }
function grant(){ fetch('/admin/grant',{method:'POST',headers:H(),body:JSON.stringify({uid:parseInt(document.getElementById('uid').value||'0'), n:parseInt(document.getElementById('n').value||'0')})}).then(r=>r.json()).then(j=>document.getElementById('grant_out').textContent=JSON.stringify(j,null,2)).catch(e=>alert(e)); }
function wset(v){ fetch('/admin/whitelist',{method:'POST',headers:H(),body:JSON.stringify({uid:parseInt(document.getElementById('wuid').value||'0'), value:!!v})}).then(r=>r.json()).then(j=>document.getElementById('wl_out').textContent=JSON.stringify(j,null,2)).catch(e=>alert(e)); }
function lookup(){ const id=parseInt(document.getElementById('luid').value||'0'); fetch('/admin/user?uid='+id,{headers:H()}).then(r=>r.json()).then(j=>document.getElementById('look_out').textContent=JSON.stringify(j,null,2)).catch(e=>alert(e)); }
function loadwl(){ fetch('/admin/whitelist',{headers:H()}).then(r=>r.json()).then(j=>document.getElementById('list_out').textContent=JSON.stringify(j,null,2)).catch(e=>alert(e)); }
</script>
</body></html>`
}
