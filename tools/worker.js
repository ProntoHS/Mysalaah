// The service the mats check in with, and nothing else.
//
// WHAT IT KNOWS, which is the whole design. One row per mat that has opted in: a random
// 32-character name the mat made for itself, and a latitude and longitude ROUNDED TO WHOLE
// DEGREES. A whole degree is about 70 miles, which on a 400px globe is a pixel and a bit --
// the difference between a country and a street, for no cost to the picture.
//
// WHAT IT DOES NOT KNOW. No IP address is stored. No name, no settings, no prayer times, no
// language, nothing a mat does. The public /mats reply carries COORDINATES ONLY and never an
// install id, so reading it tells you where mats are and not which is which.
//
// A ROW DIES ON ITS OWN after 60 days. A mat that is switched off, or thrown away, or opted
// out while the wifi was down, stops being counted without anybody having to tidy up. A mat
// still in use re-checks in long before then.
//
// AND OPTING OUT DELETES, rather than stopping sending. The switch on the mat destroys the
// id, and the mat calls DELETE on its way out so the row goes too. "Stop counting me" has to
// mean the row is gone, or the switch is a lie.

const INSTALL_ID = /^[0-9a-f]{32}$/;

// 60 days. Long enough that a mat put away for Ramadan comes back to its own row; short
// enough that the count means "mats in use" and not "mats ever switched on".
const KEEP_FOR = 60 * 60 * 24 * 60;

function reply(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      // Never cached: the count is small and wrong answers linger.
      "cache-control": "no-store",
    },
  });
}

// Whole degrees, and rounded HERE as well as on the mat. The mat rounds before it sends, so
// nothing finer ever leaves a house; this is the second lock, for the day some future version
// of the mat forgets to.
function wholeDegrees(n, limit) {
  if (typeof n !== "number" || !Number.isFinite(n)) return null;
  const rounded = Math.round(n);
  return rounded < -limit || rounded > limit ? null : rounded;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (!env.MATS) {
      return reply({ error: "no KV namespace bound as MATS" }, 500);
    }

    // Every mat on the map, for the globe to draw.
    if (request.method === "GET" && url.pathname === "/mats") {
      const listed = await env.MATS.list({ limit: 1000 });
      const mats = [];
      for (const key of listed.keys) {
        // The coordinates live in the key's metadata, so one list call answers the whole
        // question. If a row has none -- an older row, or a Cloudflare that does not hand
        // metadata back from list -- fall back to reading the row itself rather than
        // dropping a mat off the map.
        let where = key.metadata;
        if (!where || typeof where.lat !== "number" || typeof where.lon !== "number") {
          where = await env.MATS.get(key.name, "json");
        }
        if (where && Number.isInteger(where.lat) && Number.isInteger(where.lon)) {
          mats.push({ lat: where.lat, lon: where.lon });
        }
      }
      return reply({ count: mats.length, mats, truncated: listed.list_complete === false });
    }

    if (url.pathname === "/checkin" &&
        (request.method === "POST" || request.method === "DELETE")) {
      let said;
      try {
        said = await request.json();
      } catch {
        return reply({ error: "not json" }, 400);
      }
      const id = typeof said?.id === "string" ? said.id : "";
      if (!INSTALL_ID.test(id)) {
        return reply({ error: "not an install id" }, 400);
      }
      const key = "mat:" + id;

      if (request.method === "DELETE") {
        await env.MATS.delete(key);
        return reply({ gone: true });
      }

      const lat = wholeDegrees(said.lat, 90);
      const lon = wholeDegrees(said.lon, 180);
      if (lat === null || lon === null) {
        return reply({ error: "not a place on earth" }, 400);
      }

      // The day and not the moment. Enough to see that mats are alive, not enough to build a
      // picture of when a household prays.
      const day = new Date().toISOString().slice(0, 10);
      await env.MATS.put(key, JSON.stringify({ lat, lon, at: day }), {
        expirationTtl: KEEP_FOR,
        metadata: { lat, lon },
      });
      return reply({ counted: true });
    }

    return reply({ error: "nothing here" }, 404);
  },
};
