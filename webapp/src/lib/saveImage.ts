// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _tg = () => (window.Telegram?.WebApp as any)

/**
 * Save an image to the user's phone.
 *
 * Priority:
 *  1. Telegram Bot API 8.0+ downloadFile — native, no CORS, no fetch
 *  2. Web Share API (iOS → "Save Image" in share sheet, Android → gallery)
 *     — fetches via same-origin /api/v1/proxy-image to avoid CORS in WKWebView
 *  3. Blob URL <a download> fallback
 */
export async function saveImageToPhone(url: string): Promise<void> {
  if (!url) throw new Error('no url')

  const filename = `imodel-${Date.now()}.jpg`

  // 1. Telegram native download — works in all Telegram versions with Bot API 8.0+
  //    Does not require fetch() at all, Telegram handles it natively.
  const tg = _tg()
  if (tg?.downloadFile) {
    tg.downloadFile({ url, file_name: filename })
    return
  }

  // 2. Proxy fetch (same-origin → no CORS in Telegram's WKWebView)
  const proxyUrl = `/api/v1/proxy-image?url=${encodeURIComponent(url)}`
  const res = await fetch(proxyUrl)
  if (!res.ok) throw new Error(`proxy ${res.status}`)
  const blob = await res.blob()
  const ext = blob.type.includes('png') ? 'png' : 'jpg'
  const fname = `imodel-${Date.now()}.${ext}`
  const file = new File([blob], fname, { type: blob.type })

  // 2a. Web Share API — iOS: share sheet → "Save Image" to Camera Roll
  if (typeof navigator.share === 'function' && navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file] })
    return
  }

  // 3. Blob URL download fallback
  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = fname
  a.click()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
