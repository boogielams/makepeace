export default function handler(req, res) {
  res.setHeader("Cache-Control", "public, max-age=60");
  res.status(200).json({
    mapboxToken: process.env.MAPBOX_TOKEN || ""
  });
}
