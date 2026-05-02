import * as fs from "fs"
import * as https from "https"
import * as os from "os"
import * as path from "path"

interface TelegramConfig {
	bot_token: string
	chat_id: string
	poll_timeout_seconds: number
}

function loadConfig(): TelegramConfig | null {
	const configPath = path.join(os.homedir(), ".claude", "remote_approval.json")
	try {
		return JSON.parse(fs.readFileSync(configPath, "utf8"))
	} catch {
		return null
	}
}

function httpsPost(url: string, body: object): Promise<any> {
	return new Promise((resolve, reject) => {
		const data = JSON.stringify(body)
		const u = new URL(url)
		const req = https.request(
			{
				hostname: u.hostname,
				path: u.pathname,
				method: "POST",
				headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(data) },
				rejectUnauthorized: false, // handles corporate HTTPS proxies
			},
			(res) => {
				let raw = ""
				res.on("data", (c) => (raw += c))
				res.on("end", () => {
					try {
						resolve(JSON.parse(raw))
					} catch {
						reject(new Error("Bad JSON"))
					}
				})
			},
		)
		req.on("error", reject)
		req.setTimeout(35000, () => {
			req.destroy()
			reject(new Error("Timeout"))
		})
		req.write(data)
		req.end()
	})
}

async function apiCall(token: string, method: string, payload: object): Promise<any> {
	return httpsPost(`https://api.telegram.org/bot${token}/${method}`, payload)
}

async function sendMessage(token: string, chatId: string, text: string, replyMarkup: object): Promise<number | null> {
	try {
		const r = await apiCall(token, "sendMessage", {
			chat_id: chatId,
			text,
			parse_mode: "HTML",
			reply_markup: replyMarkup,
		})
		return r.ok ? r.result.message_id : null
	} catch {
		return null
	}
}

async function editMessage(token: string, chatId: string, messageId: number, text: string): Promise<void> {
	try {
		await apiCall(token, "editMessageText", { chat_id: chatId, message_id: messageId, text, parse_mode: "HTML" })
	} catch {}
}

async function answerCallback(token: string, callbackQueryId: string): Promise<void> {
	try {
		await apiCall(token, "answerCallbackQuery", { callback_query_id: callbackQueryId })
	} catch {}
}

async function getUpdates(token: string, offset: number, timeout: number): Promise<{ updates: any[]; offset: number }> {
	try {
		const r = await apiCall(token, "getUpdates", { offset, timeout, limit: 10 })
		if (!r.ok) return { updates: [], offset }
		const updates: any[] = r.result || []
		const nextOffset = updates.length ? updates[updates.length - 1].update_id + 1 : offset
		return { updates, offset: nextOffset }
	} catch {
		return { updates: [], offset }
	}
}

/**
 * Sends a Telegram approval notification for a Cline tool ask and polls for a response
 * in the background. Runs in parallel with the VS Code dialog — whichever the user
 * responds to first wins. Call the returned stop() function when VS Code dialog resolves.
 */
export function startTelegramApprovalWatcher(
	askType: string,
	text: string,
	taskId: string,
	project: string,
	onDecision: (approved: boolean) => void,
): () => void {
	const config = loadConfig()
	if (!config) return () => {}

	const { bot_token: token, chat_id: chatId, poll_timeout_seconds: totalTimeout = 300 } = config
	const sessionId = `${taskId.slice(-8)}-${Date.now()}`

	let stopped = false
	const stop = () => {
		stopped = true
	}

	const msgText =
		`<b>Cline wants to use <code>${askType}</code></b>\n\n` +
		(text ? `<code>${text.slice(0, 300)}</code>\n\n` : "") +
		`Project: <code>${project}</code>`

	const replyMarkup = {
		inline_keyboard: [
			[
				{ text: "✅ Approve", callback_data: `approve:${sessionId}` },
				{ text: "❌ Deny", callback_data: `deny:${sessionId}` },
			],
		],
	}

	;(async () => {
		try {
			// Drain stale updates before sending so we don't pick up old callbacks
			const { offset: startOffset } = await getUpdates(token, -1, 0)

			const messageId = await sendMessage(token, chatId, msgText, replyMarkup)
			if (!messageId || stopped) return

			const deadline = Date.now() + totalTimeout * 1000
			let offset = startOffset

			while (!stopped && Date.now() < deadline) {
				const pollSecs = Math.max(1, Math.min(5, Math.floor((deadline - Date.now()) / 1000)))
				const { updates, offset: nextOffset } = await getUpdates(token, offset, pollSecs)
				offset = nextOffset

				for (const update of updates) {
					const cq = update.callback_query
					if (!cq) continue
					if (cq.message?.message_id !== messageId) continue
					const data: string = cq.data || ""
					if (data !== `approve:${sessionId}` && data !== `deny:${sessionId}`) continue

					if (stopped) return
					stopped = true
					const approved = data.startsWith("approve")
					await answerCallback(token, cq.id)
					const status = approved ? "✅ Approved via Telegram" : "❌ Denied via Telegram"
					await editMessage(token, chatId, messageId, msgText + `\n\n<i>${status}</i>`)
					onDecision(approved)
					return
				}
			}

			// Timed out — update message and do nothing (VS Code dialog stays open)
			if (!stopped && messageId) {
				await editMessage(token, chatId, messageId, msgText + "\n\n<i>⏱ Timed out — respond in VS Code</i>")
			}
		} catch {
			// Never throw — background side-effect only
		}
	})()

	return stop
}
