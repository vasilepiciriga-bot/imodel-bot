/**
 * Save an image URL directly to the user's phone camera roll.
 *
 * Priority:
 *  1. Web Share API with File — iOS shows "Save Image", Android shows "Save to gallery"
 *  2. Telegram Bot API 8.0 downloadFile (saves to device Downloads / Files)
 *  3. Blob URL <a download> fallback (triggers browser download dialog)
 *
 * Replicate CDN URLs respond with Access-Control-Allow-Origin: * so cross-origin
 * fetch() works without a proxy.
 */
export async function saveImageToPhone(url: string): Promise<void> {
  const res = await fetch(url)
  const blob = await res.blob()
  const ext = blob.type.includes('png') ? 'png' : 'jpg'
  const filename = `imodel-${Date.now()}.${ext}`
  const file = new File([blob], filename, { type: blob.type })

  if (typeof navigator.share === 'function' && navigator.canShare?.({ files: [file] })) {
    await navigator.share({ files: [file] })
    return
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const tg = (window.Telegram?.WebApp as any)
  if (tg?.downloadFile) {
    tg.downloadFile({ url, file_name: filename })
    return
  }

  const blobUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = blobUrl
  a.download = filename
  a.click()
  setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
}
