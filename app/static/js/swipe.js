/* Swipe a list row left to reveal its actions, on phones. The ⋯ menu is hidden at
   that width, so without this the only way to act on a row is to open it.

   vrSwipe.attach(tbody, actionsFor)  rows must be tr[data-swipe]; actionsFor(tr)
   returns [{label, tone: 'pos' | 'neg' | '', run(tr) | href}].
   vrSwipe.snack(text, undoFn)        a short message with "Atsaukt", for deletes. */
(function () {
    'use strict';
    var phone = window.matchMedia('(max-width: 768px)');
    var BTN = 84;  // px per action

    function setX(row, x) {
        row.style.setProperty('--sx', x + 'px');
        row.style.setProperty('--sw', Math.max(0, -x) + 'px');
    }

    function attach(tbody, actionsFor) {
        if (!tbody) return;
        var open = null, drag = null, swallowClick = false;

        function build(row) {
            var cell = row.querySelector(':scope > td.c-swipe');
            if (!cell) { cell = document.createElement('td'); cell.className = 'c-swipe'; row.appendChild(cell); }
            cell.textContent = '';
            var acts = actionsFor(row) || [];
            acts.forEach(function (a) {
                var el = document.createElement(a.href ? 'a' : 'button');
                el.className = 'swipe-btn' + (a.tone ? ' is-' + a.tone : '');
                el.textContent = a.label;
                if (a.href) el.href = a.href;
                else {
                    el.type = 'button';
                    el.addEventListener('click', function (e) {
                        e.preventDefault(); e.stopPropagation();
                        close(row, true);
                        a.run(row);
                    });
                }
                cell.appendChild(el);
            });
            return acts.length * BTN;
        }

        function close(row, animate) {
            if (!row) return;
            row.classList.toggle('swipe-anim', !!animate);
            setX(row, 0);
            row.classList.remove('swipe-open');
            if (open === row) open = null;
        }

        function snap(row, max, x) {
            row.classList.add('swipe-anim');
            if (x < -max / 2) { setX(row, -max); row.classList.add('swipe-open'); open = row; }
            else close(row, true);
        }

        tbody.addEventListener('pointerdown', function (e) {
            if (!phone.matches || (e.pointerType === 'mouse' && e.button !== 0)) return;
            var row = e.target.closest('tr[data-swipe]');
            if (!row || e.target.closest('.c-swipe')) return;
            if (open && open !== row) { close(open, true); swallowClick = true; }
            drag = { row: row, id: e.pointerId, x0: e.clientX, y0: e.clientY,
                     base: row === open ? -(row._swMax || 0) : 0, axis: null, x: 0 };
        });

        tbody.addEventListener('pointermove', function (e) {
            if (!drag || e.pointerId !== drag.id) return;
            var dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
            if (!drag.axis) {
                if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
                drag.axis = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
                if (drag.axis !== 'x') { drag = null; return; }
                drag.row._swMax = build(drag.row);
                drag.row.classList.remove('swipe-anim');
                drag.row.classList.add('swiping');
                try { drag.row.setPointerCapture(e.pointerId); } catch (err) {}
            }
            var max = drag.row._swMax, x = drag.base + dx;
            // Past the actions it resists instead of stopping dead
            if (x < -max) x = -max + (x + max) * 0.25;
            if (x > 0) x = x * 0.25;
            drag.x = x;
            setX(drag.row, x);
        });

        function end(e) {
            if (!drag || e.pointerId !== drag.id) return;
            var d = drag; drag = null;
            if (d.axis !== 'x') return;
            d.row.classList.remove('swiping');
            snap(d.row, d.row._swMax, d.x);
            swallowClick = true;
        }
        tbody.addEventListener('pointerup', end);
        tbody.addEventListener('pointercancel', end);

        // A swipe, or a tap that closes an open row, must not also open the document
        tbody.addEventListener('click', function (e) {
            if (e.target.closest('.c-swipe')) return;
            if (swallowClick || open) {
                e.preventDefault(); e.stopPropagation();
                swallowClick = false;
                if (open) close(open, true);
            }
        }, true);
        document.addEventListener('pointerdown', function (e) {
            if (open && !open.contains(e.target)) close(open, true);
        });
        phone.addEventListener && phone.addEventListener('change', function () { if (open) close(open, false); });
    }

    var snackTimer = null;
    function snack(text, undo) {
        var el = document.getElementById('vrSnack');
        if (!el) {
            el = document.createElement('div');
            el.id = 'vrSnack'; el.className = 'vr-snack'; el.setAttribute('role', 'status');
            document.body.appendChild(el);
        }
        el.textContent = '';
        var span = document.createElement('span'); span.textContent = text; el.appendChild(span);
        if (undo) {
            var b = document.createElement('button'); b.type = 'button'; b.textContent = 'Atsaukt';
            b.addEventListener('click', function () { el.hidden = true; clearTimeout(snackTimer); undo(); });
            el.appendChild(b);
        }
        el.hidden = false;
        clearTimeout(snackTimer);
        snackTimer = setTimeout(function () { el.hidden = true; }, 6000);
    }

    window.vrSwipe = { attach: attach, snack: snack };
})();
