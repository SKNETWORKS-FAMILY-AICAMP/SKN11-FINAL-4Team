import { Badge } from "@/components/ui/badge"
import { Instagram, Globe } from "lucide-react"

interface PlatformBadgeProps {
  platform: 'instagram'
  isConnected: boolean
  username?: string
  className?: string
}

export function PlatformBadge({ platform, isConnected, username, className = "" }: PlatformBadgeProps) {
  const getPlatformInfo = () => {
    switch (platform) {
      case 'instagram':
        return {
          icon: Instagram,
          label: 'Instagram',
          color: isConnected ? 'bg-gradient-to-r from-purple-500 to-pink-500' : 'bg-gray-100',
          textColor: isConnected ? 'text-white' : 'text-gray-600'
        }
      default:
        return {
          icon: Globe,
          label: 'Platform',
          color: 'bg-gray-100',
          textColor: 'text-gray-600'
        }
    }
  }

  const platformInfo = getPlatformInfo()
  const IconComponent = platformInfo.icon

  return (
    <Badge 
      className={`flex items-center gap-1 px-2 py-1 text-xs font-medium ${platformInfo.color} ${platformInfo.textColor} ${className}`}
    >
      <IconComponent className="h-3 w-3" />
      {username && isConnected && (
        <span className="ml-1 opacity-80">@{username}</span>
      )}
    </Badge>
  )
} 