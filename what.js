const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion
} = require("@whiskeysockets/baileys");

const P = require("pino");
const fs = require("fs");
const qrcode = require("qrcode-terminal");

// ─── Suppress libsignal / Baileys internal noise ──────────────────────────────
const NOISE = [
    "Bad MAC", "Failed to decrypt", "Session error", "Closing open session",
    "Closing session", "SessionEntry", "SessionCipher", "verifyMAC",
    "decryptWithSessions", "doDecryptWhisperMessage", "node_modules/libsignal",
    "node_modules/@whiskeysockets", "<Buffer", "registrationId", "currentRatchet",
    "ephemeralKeyPair", "lastRemoteEphemeral", "previousCounter", "indexInfo",
    "baseKeyType", "remoteIdentityKey", "pendingPreKey", "chainKey", "chainType",
    "_chains", "pubKey", "privKey", "rootKey", "baseKey", "signedKeyId", "preKeyId",
    "at Object.", "at async "
];
const _log = console.log;
const _err = console.error;
const _warn = console.warn;
const isNoise = (...args) => {
    const s = args.map(a => typeof a === "object" ? JSON.stringify(a) : String(a)).join(" ");
    return NOISE.some(p => s.includes(p));
};
console.log = (...a) => { if (!isNoise(...a)) _log(...a); };
console.error = (...a) => { if (!isNoise(...a)) _err(...a); };
console.warn = (...a) => { if (!isNoise(...a)) _warn(...a); };

// ─── IST helper (UTC+5:30) ────────────────────────────────────────────────────
const toIST = (ts) => new Date(ts).toLocaleString("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: true
});
const nowIST = () => toIST(Date.now());

// ─── Config ───────────────────────────────────────────────────────────────────
const CONFIG_FILE = "./config.json";
const REPLIES_FILE = "./replies.json";

const DEFAULT_AUTOREPLY =
    "Hey there!\u270c\ufe0f\n\n" +
    "I'm currently away from my phone and might not be able to respond immediately. " +
    "But don't worry - I'll get back to you as soon as I'm available! \u26a1\n\n" +
    "*Please note:* If it's urgent, feel free to call me directly. " +
    "Otherwise, I'll reply to your message shortly.\n\n" +
    "Have a great day! \u2728";

let config = {
    owner: "917983186356",
    ownerLid: "57801703485591",
    autoreply: DEFAULT_AUTOREPLY,
    cooldown: 86400000,   // 24 hours in ms
    enabled: true,
    blacklist: []
};

// Load saved config (merge so new keys always exist)
if (fs.existsSync(CONFIG_FILE)) {
    try {
        const saved = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf8"));
        config = { ...config, ...saved };
    } catch (e) {
        _err("Bad config.json, using defaults");
    }
}
// Remove legacy ignoreGroups — groups are always ignored
delete config.ignoreGroups;

const saveConfig = () =>
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
saveConfig(); // always write clean version on start

// ─── Reply history ────────────────────────────────────────────────────────────
let lastReply = {};
if (fs.existsSync(REPLIES_FILE)) {
    try { lastReply = JSON.parse(fs.readFileSync(REPLIES_FILE, "utf8")); }
    catch (e) { _err("Bad replies.json, starting fresh"); }
}
const saveReplies = () =>
    fs.writeFileSync(REPLIES_FILE, JSON.stringify(lastReply, null, 2));

// ─── Helpers ──────────────────────────────────────────────────────────────────
// Strip everything after @ and keep only digits
const toNum = (id) => String(id || "").replace(/@.*$/, "").replace(/\D/g, "");

// Valid phone number = at least 7 digits
const isValidNum = (n) => n.length >= 7;

// Waiting-for-template state: key = ownerTarget string, value = true
const waitingForTemplate = {};

// ─── Bot ──────────────────────────────────────────────────────────────────────
async function startBot() {
    const { state, saveCreds } = await useMultiFileAuthState("session");

    let sock;
    try {
        const { version } = await fetchLatestBaileysVersion();
        sock = makeWASocket({
            logger: P({ level: "silent" }),
            auth: state,
            version,
            browser: ["AutoReplyBot", "Chrome", "1.0.0"],
            syncFullHistory: false,
            getMessage: async () => ({ conversation: "" })
        });
    } catch (err) {
        _err("Socket creation failed:", err.message);
        setTimeout(startBot, 5000);
        return;
    }

    sock.ev.on("creds.update", saveCreds);

    sock.ev.on("connection.update", async ({ connection, lastDisconnect, qr }) => {
        if (qr) {
            _log("\nScan this QR code with WhatsApp:\n");
            qrcode.generate(qr, { small: true });
            _log("\n1. Open WhatsApp on your phone");
            _log("2. Settings > Linked Devices > Link a Device");
            _log("3. Scan the QR code above\n");
        }

        if (connection === "connecting") {
            _log("[" + nowIST() + "] Connecting...");
        }

        if (connection === "close") {
            const code = lastDisconnect?.error?.output?.statusCode;
            const reason = lastDisconnect?.error?.output?.payload?.message || "Unknown";
            _log("[" + nowIST() + "] Disconnected: " + reason);
            if (code === DisconnectReason.loggedOut) {
                _log("Logged out — clearing session");
                if (fs.existsSync("session"))
                    fs.rmSync("session", { recursive: true, force: true });
                setTimeout(startBot, 2000);
            } else {
                setTimeout(startBot, code === DisconnectReason.restartRequired ? 1000 : 4000);
            }
        }

        if (connection === "open") {
            const cdDisplay = config.cooldown >= 3600000
                ? (config.cooldown / 3600000) + " hours"
                : (config.cooldown / 60000) + " minutes";
            _log("\n============================================");
            _log("   WhatsApp Auto-Reply Bot - Connected");
            _log("============================================");
            _log("  Owner    : +" + config.owner);
            _log("  IST Time : " + nowIST());
            _log("  Status   : " + (config.enabled ? "ON" : "OFF"));
            _log("  Cooldown : " + cdDisplay);
            _log("  Groups   : Always ignored");
            _log("  Records  : " + Object.keys(lastReply).length + " contacts");
            _log("--------------------------------------------");
            _log("  .change          Change auto-reply");
            _log("  .preview         View current reply");
            _log("  .status          Bot status + IST time");
            _log("  .toggle          Enable / disable bot");
            _log("  .cooldown <hrs>  e.g. .cooldown 12");
            _log("  .blacklist <num> Block a number");
            _log("  .blacklist list  List blocked numbers");
            _log("  .whitelist <num> Unblock a number");
            _log("  .reset <num>     Reset cooldown for number");
            _log("  .stats           Reply history (IST times)");
            _log("  .clearstats      Clear all history");
            _log("  .help            Show command list");
            _log("============================================\n");
        }
    });

    // Deduplicate messages
    const processedIds = new Set();

    sock.ev.on("messages.upsert", async ({ messages, type }) => {
        // Only process 'notify' type — ignore history sync / append
        if (type !== "notify") return;

        const msg = messages[0];
        if (!msg?.message) return;

        // Skip if already processed
        const msgId = msg.key.id;
        if (processedIds.has(msgId)) return;
        processedIds.add(msgId);
        // Keep set small
        if (processedIds.size > 200) {
            const first = processedIds.values().next().value;
            processedIds.delete(first);
        }

        const chatId = msg.key.remoteJid;
        if (!chatId) return;

        // Skip broadcast / newsletter / status channels
        if (
            chatId === "status@broadcast" ||
            chatId.endsWith("@newsletter") ||
            chatId.endsWith("@broadcast")
        ) return;

        const isGroup = chatId.endsWith("@g.us");
        if (isGroup) return;  // always skip groups

        // Detect owner's chat — can arrive as @lid or @s.whatsapp.net
        const isOwnerLid = chatId === (config.ownerLid + "@lid").trim();
        const isOwnerStd = chatId === (config.owner + "@s.whatsapp.net").trim();
        // More permissive owner check as a fallback
        const isOwnerChat = isOwnerLid || isOwnerStd || chatId.includes(config.owner);

        // Skip own outgoing messages UNLESS it's the owner chat (commands come as fromMe=true)
        if (msg.key.fromMe && !isOwnerChat) return;

        // Owner commands are messages the owner sends to themselves (fromMe = true in owner chat)
        const isFromOwner = isOwnerChat && msg.key.fromMe;

        const text = (
            msg.message?.conversation ||
            msg.message?.extendedTextMessage?.text ||
            msg.message?.imageMessage?.caption ||
            msg.message?.videoMessage?.caption ||
            ""
        ).trim();

        if (isOwnerChat && text === "") return; // skip empty echo events


        // Where to send owner command replies
        // Always reply via standard phone number format — @lid receives but can't be sent to reliably
        const ownerTarget = config.owner + "@s.whatsapp.net";

        const replyOwner = async (body) => {
            try {
                await sock.sendMessage(ownerTarget, { text: body });
                _log("Sent to owner via:", ownerTarget);
            } catch (e) {
                _err("Failed to send to owner:", e.message);
            }
        };



        // =========================================================================
        // OWNER COMMANDS
        // =========================================================================
        if (isFromOwner) {

            // ── .change (step 1) ──────────────────────────────────────────────────
            if (text === ".change") {
                waitingForTemplate[ownerTarget] = Math.floor(Date.now() / 1000); // store in seconds like WhatsApp // store timestamp, not just true
                await replyOwner(
                    "*Send your new auto-reply message now.*\n" +
                    "Type anything and send. Send .cancel to abort."
                );
                _log("[" + nowIST() + "] .change — waiting for new template");
                return;
            }

            // ── Capture new template (step 2) ─────────────────────────────────────
            // Must check BEFORE other commands so the template text isn't misrouted
            // ── Capture new template (step 2) ─────────────────────────────────────
            if (waitingForTemplate[ownerTarget]) {
                const msgTs = (msg.messageTimestamp || 0);
                const changeTs = waitingForTemplate[ownerTarget];

                if (msgTs <= changeTs) return;

                if (text === ".cancel") {
                    delete waitingForTemplate[ownerTarget];
                    await replyOwner("Cancelled. Auto-reply unchanged.");
                    return;
                }
                if (text && !text.startsWith(".")) {
                    config.autoreply = text;
                    saveConfig();
                    delete waitingForTemplate[ownerTarget];
                    await replyOwner(
                        "*Auto-reply updated!*\n\n" +
                        "New message:\n" +
                        "---\n" + text + "\n---"
                    );
                    _log("[" + nowIST() + "] Auto-reply template updated");
                    return;
                }
                await replyOwner("⚠️ Still waiting for your new message. Send text or .cancel to abort.");
                return;
            }

            // ── .preview ──────────────────────────────────────────────────────────
            if (text === ".preview") {
                await replyOwner(
                    "*Current Auto-Reply:*\n---\n" + config.autoreply + "\n---"
                );
                return;
            }

            // ── .status ───────────────────────────────────────────────────────────
            if (text === ".status") {
                const cdMs = config.cooldown;
                const cdDisplay = cdMs >= 3600000
                    ? (cdMs / 3600000) + " hours"
                    : (cdMs / 60000) + " minutes";
                await replyOwner(
                    "*Bot Status*\n---\n" +
                    "Time (IST) : " + nowIST() + "\n" +
                    "Auto-reply : " + (config.enabled ? "ON" : "OFF") + "\n" +
                    "Cooldown   : " + cdDisplay + "\n" +
                    "Blacklist  : " + config.blacklist.length + " numbers\n" +
                    "Groups     : Always ignored\n" +
                    "Replied to : " + Object.keys(lastReply).length + " contacts\n" +
                    "---"
                );
                _log("[" + nowIST() + "] .status");
                return;
            }

            // ── .toggle ───────────────────────────────────────────────────────────
            if (text === ".toggle") {
                config.enabled = !config.enabled;
                saveConfig();
                await replyOwner("Auto-reply is now *" + (config.enabled ? "ON" : "OFF") + "*");
                _log("[" + nowIST() + "] Toggled " + (config.enabled ? "ON" : "OFF"));
                return;
            }

            // ── .cooldown <hrs> ───────────────────────────────────────────────────
            if (text.startsWith(".cooldown")) {
                const parts = text.trim().split(/\s+/);
                const hrs = parseFloat(parts[1]);
                if (!parts[1] || isNaN(hrs) || hrs < 0.01) {
                    await replyOwner(
                        "Usage: .cooldown 24\n" +
                        "Or: .cooldown 0.5  (= 30 minutes)\n" +
                        "Minimum: 0.01 hours"
                    );
                    return;
                }
                config.cooldown = Math.round(hrs * 3600000);
                saveConfig();
                const disp = hrs < 1 ? Math.round(hrs * 60) + " minutes" : hrs + " hours";
                await replyOwner("Cooldown set to *" + disp + "*");
                _log("[" + nowIST() + "] Cooldown = " + disp);
                return;
            }

            // ── .blacklist list ───────────────────────────────────────────────────
            if (text === ".blacklist list") {
                if (config.blacklist.length === 0) {
                    await replyOwner("Blacklist is empty.");
                } else {
                    await replyOwner(
                        "*Blocked Numbers (" + config.blacklist.length + "):*\n---\n" +
                        config.blacklist.map((n, i) => (i + 1) + ". +" + n).join("\n") +
                        "\n---"
                    );
                }
                return;
            }

            // ── .blacklist <number> ───────────────────────────────────────────────
            if (text.startsWith(".blacklist ")) {
                const num = toNum(text.split(/\s+/)[1]);
                if (!isValidNum(num)) {
                    await replyOwner("Usage: .blacklist 919876543210");
                    return;
                }
                if (config.blacklist.includes(num)) {
                    await replyOwner("+" + num + " is already blocked.");
                } else {
                    config.blacklist.push(num);
                    saveConfig();
                    await replyOwner("Blocked: *+" + num + "*");
                    _log("[" + nowIST() + "] Blocked +" + num);
                }
                return;
            }

            // ── .whitelist <number> ───────────────────────────────────────────────
            if (text.startsWith(".whitelist ")) {
                const num = toNum(text.split(/\s+/)[1]);
                if (!isValidNum(num)) {
                    await replyOwner("Usage: .whitelist 919876543210");
                    return;
                }
                const idx = config.blacklist.indexOf(num);
                if (idx === -1) {
                    await replyOwner("+" + num + " is not in the blacklist.");
                } else {
                    config.blacklist.splice(idx, 1);
                    saveConfig();
                    await replyOwner("Unblocked: *+" + num + "*");
                    _log("[" + nowIST() + "] Unblocked +" + num);
                }
                return;
            }

            // ── .reset <number> ───────────────────────────────────────────────────
            if (text.startsWith(".reset ")) {
                const num = toNum(text.split(/\s+/)[1]);
                if (!isValidNum(num)) {
                    await replyOwner("Usage: .reset 919876543210");
                    return;
                }
                if (lastReply[num] !== undefined) {
                    delete lastReply[num];
                    saveReplies();
                    await replyOwner("Reset cooldown for *+" + num + "*\nThey will get auto-reply next message.");
                    _log("[" + nowIST() + "] Reset cooldown for +" + num);
                } else {
                    await replyOwner("No cooldown record for +" + num);
                }
                return;
            }

            // ── .stats ────────────────────────────────────────────────────────────
            if (text === ".stats") {
                const entries = Object.entries(lastReply);
                let out = "*Reply Statistics* (IST)\n---\n";
                if (entries.length === 0) {
                    out += "No replies sent yet.";
                } else {
                    const sorted = entries.sort((a, b) => b[1] - a[1]);
                    out += "Total: *" + sorted.length + "* contacts\n\n";
                    sorted.slice(0, 15).forEach(([num, ts], i) => {
                        out += (i + 1) + ". +" + num + "\n";
                        out += "   " + toIST(ts) + "\n\n";
                    });
                    if (sorted.length > 15)
                        out += "...and " + (sorted.length - 15) + " more";
                }
                await replyOwner(out + "\n---");
                _log("[" + nowIST() + "] .stats");
                return;
            }

            // ── .clearstats ───────────────────────────────────────────────────────
            if (text === ".clearstats") {
                const count = Object.keys(lastReply).length;
                lastReply = {};
                saveReplies();
                await replyOwner(
                    "Cleared history for *" + count + "* contacts.\n" +
                    "Everyone will get auto-reply on next message."
                );
                _log("[" + nowIST() + "] Cleared " + count + " records");
                return;
            }

            // ── .help ─────────────────────────────────────────────────────────────
            if (text === ".help") {
                await replyOwner(
                    "*Bot Commands*\n" +
                    "---\n" +
                    ".change          Change auto-reply message\n" +
                    ".preview         View current auto-reply\n" +
                    ".status          Status + current IST time\n" +
                    ".toggle          Turn bot ON or OFF\n" +
                    ".cooldown <hrs>  Set wait between replies\n" +
                    ".blacklist <num> Block a contact\n" +
                    ".blacklist list  Show all blocked contacts\n" +
                    ".whitelist <num> Unblock a contact\n" +
                    ".reset <num>     Reset cooldown for contact\n" +
                    ".stats           View reply history\n" +
                    ".clearstats      Clear all reply history\n" +
                    ".help            Show this list\n" +
                    "---\n" +
                    "Groups are always ignored."
                );
                _log("[" + nowIST() + "] .help");
                return;
            }

            // Unknown dot-command — silently ignore
            if (text.startsWith(".")) return;

            // Non-command message in owner chat — ignore
            return;
        }
        // =========================================================================
        // END OWNER COMMANDS
        // =========================================================================

        // From here: regular incoming messages from other people

        // Skip owner's own chat for auto-reply
        if (isOwnerChat) return;

        // Skip own outgoing messages
        if (msg.key.fromMe) return;

        // Skip blacklisted numbers
        const senderNum = toNum(chatId);
        if (!isValidNum(senderNum)) return;  // skip anything without a real number
        if (config.blacklist.includes(senderNum)) return;

        // Skip if bot is disabled
        if (!config.enabled) return;

        // Skip command-like messages from contacts
        if (text.startsWith(".")) return;

        // ── Auto-reply with cooldown ───────────────────────────────────────────
        const now = Date.now();
        const lastTime = lastReply[senderNum];
        const ready = !lastTime || (now - lastTime > config.cooldown);

        if (ready) {
            const delay = 500 + Math.floor(Math.random() * 1500);
            setTimeout(async () => {
                try {
                    await sock.sendMessage(chatId, { text: config.autoreply });
                    lastReply[senderNum] = now;
                    saveReplies();
                    const cdHrs = (config.cooldown / 3600000).toFixed(1);
                    _log(
                        "[" + nowIST() + "] Replied to +" + senderNum +
                        " | delay: " + delay + "ms | next in: " + cdHrs + "hrs"
                    );
                } catch (err) {
                    _err("[" + nowIST() + "] Reply failed to +" + senderNum + ":", err.message);
                }
            }, delay);
        } else {
            const minLeft = Math.ceil((config.cooldown - (now - lastTime)) / 60000);
            _log("[" + nowIST() + "] Skipped +" + senderNum + " (" + minLeft + "min cooldown left)");
        }
    });
}

_log("Starting WhatsApp Auto-Reply Bot...\n");
startBot().catch(_err);