/* The document paper in HTML, laid out exactly like the PDF (app/pdf_generator.py):
   an A4 page 595 px wide, so every PDF point is one pixel, scaled to its box.
   Used by the editor's live preview and the document page; change both together.

   vrPaper.render(el, d)  d = {
     template: 'classic' | 'modern' | 'minimal', kind: 'sell' | 'credit' | 'buy' | 'offer',
     title, number, date, due,                       (dates already dd.mm.yyyy)
     ref,                                            ("Kredītrēķins rēķinam Nr. … no …" or '')
     supplier, buyer: { name, reg, vat, addr, bank, account, person, ref },
     items: [{ name, unit, qty, price, included, amount }],   (amount: the stored line total, if known)
     subtotal, vatRate, vat, rounding, total, vatPayer, reverseCharge,
     notes, electronic, accent, logo (url or ''), logoWidth (%), contacts: [], free }
*/
(function () {
    'use strict';
    var PAGE_W = 595;
    var esc = function (s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    };
    // SIA "Bērzu Darbnīca" -> SIA „Bērzu Darbnīca”, as the PDF prints names
    function quotes(s) {
        var open = true;
        return String(s || '').replace(/"/g, function () { var q = open ? '„' : '”'; open = !open; return q; });
    }
    var eq = function (s) { return esc(quotes(s)); };
    var nl = function (s) { return esc(String(s || '').trim()).replace(/\r?\n/g, '<br>'); };
    function iban(a) {
        var raw = String(a || '').replace(/\s/g, '');
        return /^[A-Za-z]{2}\d{2}/.test(raw) && raw.length > 12 ? raw.replace(/(.{4})/g, '$1 ').trim() : String(a || '');
    }
    function isLight(hex) {
        var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
        if (!m) return false;
        var n = parseInt(m[1], 16), r = (n >> 16) / 255, g = ((n >> 8) & 255) / 255, b = (n & 255) / 255;
        return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.62;
    }
    function tint(hex, a) {
        var m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
        if (!m) return '#f1f2f4';
        var n = parseInt(m[1], 16);
        var mix = function (c) { return Math.round(255 - (255 - c) * a); };
        return 'rgb(' + mix(n >> 16) + ',' + mix((n >> 8) & 255) + ',' + mix(n & 255) + ')';
    }
    var money = function (v) { return window.fmtEur ? fmtEur(v) : Number(v || 0).toFixed(2) + ' €'; };
    var num = function (v) { return window.fmtNum ? fmtNum(v) : Number(v || 0).toFixed(2); };
    var qty = function (v) { return window.fmtQty ? fmtQty(v) : String(v); };
    var unitPrice = function (v) { return window.fmtPrice ? fmtPrice(v) : num(v); };
    // A line's amount as stored, else as app/money.py would round it
    var lineAmount = function (it) {
        if (it.amount != null) return it.amount;
        return window.vrLine ? vrLine(it.qty, it.price) : it.qty * it.price;
    };
    var amountLabel = function (kind) {
        return kind === 'sell' ? 'Apmaksai' : kind === 'credit' ? 'Kreditētā summa' : 'Kopā';
    };

    function identity(d) {
        if (d.logo && d.kind !== 'buy') {
            var pct = Math.max(40, Math.min(160, Number(d.logoWidth) || 100)) / 100;
            var box = d.template === 'minimal' ? [108, 37] : [130, 48];
            return '<img class="pp-logo" src="' + esc(d.logo) + '" alt="" style="max-width:' + Math.round(box[0] * pct) + 'px;max-height:' + Math.round(box[1] * pct) + 'px">';
        }
        return '<div class="pp-wordmark">' + eq(d.supplier.name || ' ') + '</div>';
    }
    function label(t) { return '<div class="pp-label">' + esc(t) + '</div>'; }
    function kv(rows, cls) {
        return '<table class="pp-kv ' + (cls || '') + '">' + rows.map(function (r) {
            return '<tr><td class="k">' + esc(r[0]) + '</td><td class="v">' + r[1] + '</td></tr>';
        }).join('') + '</table>';
    }
    function metaRows(d) {
        var rows = [['Numurs', esc(d.number)], ['Datums', esc(d.date || '—')]];
        if (d.due) rows.push(['Apmaksāt līdz', esc(d.due)]);
        return rows;
    }

    function head(d) {
        if (d.template === 'modern') {
            var cells = [[amountLabel(d.kind), money(d.total)]];
            if (d.due) cells.push(['Apmaksāt līdz', esc(d.due)]);
            cells.push(['Datums', esc(d.date || '—')]);
            var light = isLight(d.accent);
            return '<div class="pp-top"><div>' + identity(d) + '</div><div class="pp-title">' + esc(d.title) +
                '<small>Nr. ' + esc(d.number) + '</small></div></div>' +
                '<div class="pp-panel' + (light ? ' light' : '') + '" style="background:' + esc(d.accent) + '">' +
                cells.map(function (c, i) {
                    return '<div class="' + (i ? 'c' : 'c big') + '"><span>' + c[0] + '</span><b>' + c[1] + '</b></div>';
                }).join('') + '</div>';
        }
        if (d.template === 'minimal') {
            return '<div class="pp-top">' + identity(d) + '</div>' +
                '<div class="pp-marker" style="background:' + esc(d.accent) + '"></div>' +
                '<div class="pp-title">' + esc(d.title) + ' <span>' + esc(d.number) + '</span></div>';
        }
        return '<div class="pp-top">' + identity(d) + '</div>' +
            '<div class="pp-titlerow"><div class="pp-title">' + esc(d.title) + '</div>' + kv(metaRows(d), 'meta') + '</div>' +
            '<div class="pp-double" style="border-color:' + esc(d.accent) + '"></div>';
    }

    function party(d, title, p) {
        var lines = [];
        if (p.reg) lines.push((p.person ? 'P. k. ' : 'Reģ. Nr. ') + p.reg);
        if (p.vat && d.vatPayer) lines.push('PVN Nr. ' + p.vat);
        if (p.addr) lines.push(p.addr);
        if (p.ref) lines.push('Atsauce: ' + p.ref);  // the buyer's reference (BT-10)
        return '<div class="pp-party">' + label(title) + '<div class="pp-name">' + eq(p.name || '—') + '</div>' +
            (lines.length ? '<div class="pp-muted">' + lines.map(eq).join('<br>') + '</div>' : '') + '</div>';
    }
    function parties(d) {
        var third = d.template === 'minimal'
            ? '<div class="pp-party">' + label('Datumi') + kv(metaRows(d).slice(1)) + '</div>' : '';
        return '<div class="pp-parties">' + party(d, 'Piegādātājs', d.supplier) + party(d, 'Saņēmējs', d.buyer) + third + '</div>';
    }

    function lines(d) {
        var rows = d.items.length ? d.items.map(function (it, i) {
            var right = it.included
                ? '<td class="r m" colspan="2">iekļauts cenā</td>'
                : '<td class="r">' + unitPrice(it.price) + '</td><td class="r">' + num(lineAmount(it)) + '</td>';
            return '<tr><td class="m">' + (i + 1) + '</td><td>' + nl(it.name) + '</td><td class="r">' + qty(it.qty) +
                '</td><td class="m u">' + esc(it.unit) + '</td>' + right + '</tr>';
        }).join('') : '<tr><td></td><td class="m">Nav rindu</td><td></td><td></td><td></td><td></td></tr>';
        var headStyle = d.template === 'modern'
            ? ' style="background:' + (isLight(d.accent) ? tint(d.accent, 0.35) : tint(d.accent, 0.07)) + '"' : '';
        return '<table class="pp-lines"><colgroup><col class="c-nr"><col><col class="c-q"><col class="c-u"><col class="c-p"><col class="c-s"></colgroup>' +
            '<thead><tr' + headStyle + '><th>Nr.</th><th>Apraksts</th><th class="r">Daudz.</th><th class="u">Mērv.</th><th class="r">Cena</th><th class="r">Summa</th></tr></thead>' +
            '<tbody>' + rows + '</tbody></table>';
    }

    function payment(d) {
        var s = d.supplier;
        if (d.kind !== 'sell' || !s.account) return '';
        var rows = [];
        if (s.bank) rows.push(['Banka', eq(s.bank)]);
        rows.push(['Konts', esc(iban(s.account))]);
        rows.push(['Maksājuma mērķis', esc(d.title + ' Nr. ' + d.number)]);
        if (d.due && d.template !== 'modern') rows.push(['Apmaksāt līdz', esc(d.due)]);
        return '<div class="pp-pay">' + label('Maksājuma informācija') + kv(rows) + '</div>';
    }
    function totals(d) {
        var html = '';
        if (d.vatPayer) {
            var rows = d.reverseCharge
                ? [['Summa bez PVN', money(d.subtotal)], ['Nodokļa apgrieztā maksāšana', '—']]
                : [['Summa bez PVN', money(d.subtotal)], ['PVN ' + qty(d.vatRate) + ' %', money(d.vat)]];
            if (Number(d.rounding)) rows.push(['Noapaļošana', money(d.rounding)]);
            html += '<table class="pp-sums">' + rows.map(function (r) {
                return '<tr><td>' + esc(r[0]) + '</td><td class="r">' + r[1] + '</td></tr>';
            }).join('') + '</table><div class="pp-sumrule"></div>';
        }
        return '<div class="pp-totals">' + html + '<div class="pp-amount"><span>' + amountLabel(d.kind) +
            '</span><b>' + money(d.total) + '</b></div></div>';
    }
    function tail(d) {
        var out = '<div class="pp-summary">' + (payment(d) || '<div></div>') + totals(d) + '</div>';
        if (String(d.notes || '').trim()) out += '<div class="pp-notes">' + label('Piezīmes') + '<div>' + nl(d.notes) + '</div></div>';
        out += d.electronic
            ? '<div class="pp-edoc">Dokuments ir sagatavots elektroniski un ir derīgs bez paraksta.</div>'
            : '<div class="pp-sign"><div>Izsniedza</div><div>Saņēma</div></div>';
        return out;
    }
    function foot(d) {
        var own = d.kind === 'buy' ? d.buyer : d.supplier;
        var contacts = (d.contacts || []).filter(Boolean);
        return '<div class="pp-foot"><div><b>' + eq(own.name) + '</b><span>' + eq(contacts.length ? contacts.join('  ·  ') : own.addr) +
            '</span></div><div class="r"><span>' + esc(d.title + ' Nr. ' + d.number) + '</span><span>1 / 1</span></div></div>' +
            (d.free ? '<div class="pp-free">Sagatavots ar V-Rēķini · v-rekini.lv</div>' : '');
    }

    function fit(el) {
        var page = el.querySelector('.pp');
        if (!page) return;
        var w = el.clientWidth;
        if (!w) return;
        var s = w / PAGE_W;
        page.style.transform = 'scale(' + s + ')';
        el.style.height = Math.ceil(page.offsetHeight * s) + 'px';
    }
    var observed = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(function (entries) {
        entries.forEach(function (e) { fit(e.target); });
    }) : null;

    function render(el, d) {
        if (!el) return;
        d.template = ['classic', 'modern', 'minimal'].indexOf(d.template) >= 0 ? d.template : 'classic';
        d.accent = /^#[0-9a-f]{6}$/i.test(d.accent || '') ? d.accent : '#09090b';
        el.classList.add('pp-fit');
        var ref = d.ref ? '<div class="pp-ref">' + esc(d.ref) + '</div>' : '';
        el.innerHTML = '<div class="pp pp-' + d.template + '"><div class="pp-body">' + head(d) + ref + parties(d) + lines(d) + tail(d) +
            '</div>' + foot(d) + '</div>';
        fit(el);
        var img = el.querySelector('.pp-logo');
        if (img && !img.complete) img.addEventListener('load', function () { fit(el); }, { once: true });
        if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { fit(el); });
        if (observed && !el._ppObserved) { observed.observe(el); el._ppObserved = true; }
    }

    window.vrPaper = { render: render, fit: fit };
})();
