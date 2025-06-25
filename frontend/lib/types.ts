export interface AIModel {
  id: string
  name: string
  description: string
  personality: string
  tone: string
  status: "training" | "ready" | "error"
  createdAt: string
  apiKey?: string
  trainingData?: {
    textSamples: number
    voiceSamples: number
    imageSamples: number
  }
}

export interface User {
  id: string
  email: string
  company: string
  name: string
}
