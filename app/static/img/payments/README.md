# Footer payment logos

All marks shown in the public footer and on the terms page live here and are
committed. They are the merchant's official artwork; see SOURCES.txt for where
each came from and what was done to it.

They used to be hotlinked from vnmedia.lv/wp-content/uploads/. Those URLs 404'd
on 2026-08-04, which is exactly what this folder exists to prevent: a file in
git cannot 404.

A mark with no file here renders as its **name in text**. Nothing breaks, but
SEB's card-logo requirement expects the real marks, so fill any gap.

## Adding or replacing a mark

1. Copy the file in under the name `app/payment_logos.py` expects (the
   extension matters), or change that entry's `file` to match.
2. Set its `height` (footer) and `height_lg` (terms page) so it reads at the
   same optical size as its neighbours.
3. Restart the app: presence is read once at startup.

Check what is in place:

    python3 scripts/fetch_payment_logos.py --check

Missing right now: `everypay.webp`.
