// Firebase Cloud Function: https://asia-southeast1-movie-858f6.cloudfunctions.net/gemini
// ตั้งค่า key ครั้งเดียวด้วย: firebase functions:secrets:set GEMINI_API_KEY
const { onRequest } = require("firebase-functions/v2/https");
const { defineSecret } = require("firebase-functions/params");
const { handleRequest } = require("./proxy");

const GEMINI_API_KEY = defineSecret("GEMINI_API_KEY");

exports.gemini = onRequest(
  { region: "asia-southeast1", secrets: [GEMINI_API_KEY], maxInstances: 2, timeoutSeconds: 60, memory: "256MiB" },
  (req, res) => handleRequest(req, res, { apiKey: GEMINI_API_KEY.value() })
);
