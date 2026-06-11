import { useRef } from 'react'
import { Camera, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAppStore } from '../../store/appStore'

async function compressSelfie(file: File): Promise<{ b64: string; preview: string }> {
  const img = await createImageBitmap(file)
  const MAX = 1024
  const ratio = Math.min(MAX / img.width, MAX / img.height, 1)
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(img.width * ratio)
  canvas.height = Math.round(img.height * ratio)
  canvas.getContext('2d')!.drawImage(img, 0, 0, canvas.width, canvas.height)

  let quality = 0.85
  let dataUrl = canvas.toDataURL('image/jpeg', quality)
  while (dataUrl.length > 270_000 && quality > 0.5) {
    quality -= 0.1
    dataUrl = canvas.toDataURL('image/jpeg', quality)
  }
  return { b64: dataUrl.split(',')[1], preview: dataUrl }
}

export function SelfieUploader() {
  const inputRef = useRef<HTMLInputElement>(null)
  const selfiePreview = useAppStore((s) => s.selfiePreview)
  const setSelfie = useAppStore((s) => s.setSelfie)
  const clearSelfie = useAppStore((s) => s.clearSelfie)

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    const { b64, preview } = await compressSelfie(file)
    setSelfie(b64, preview)
    e.target.value = ''
  }

  return (
    <div className="relative">
      <AnimatePresence mode="wait">
        {selfiePreview ? (
          <motion.div
            key="preview"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="relative rounded-card overflow-hidden bg-gray-100"
          >
            <img src={selfiePreview} alt="selfie" className="w-full h-48 object-cover" />
            <button
              onClick={clearSelfie}
              className="absolute top-2 right-2 w-8 h-8 bg-black/50 rounded-full flex items-center justify-center"
            >
              <X size={14} className="text-white" />
            </button>
          </motion.div>
        ) : (
          <motion.button
            key="upload"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => inputRef.current?.click()}
            className="w-full h-48 border-2 border-dashed border-[#6C47FF]/30 rounded-card flex flex-col items-center justify-center gap-3 bg-[#6C47FF]/5 active:bg-[#6C47FF]/10 transition-colors"
          >
            <div className="w-14 h-14 rounded-full bg-gradient-to-br from-[#6C47FF] to-[#FF2D78] flex items-center justify-center">
              <Camera size={24} className="text-white" />
            </div>
            <div className="text-center">
              <p className="text-[15px] font-semibold text-[#1D1D1F]">Add your selfie</p>
              <p className="text-[12px] text-[#6E6E73] mt-0.5">Tap to choose from gallery</p>
            </div>
          </motion.button>
        )}
      </AnimatePresence>
      <input ref={inputRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
    </div>
  )
}
