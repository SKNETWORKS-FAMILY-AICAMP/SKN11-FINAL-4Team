import { Badge } from "@/components/ui/badge"
import { Instagram, Globe } from "lucide-react"

interface PlatformBadgeProps {
  platform: 'instagram' | 'youtube' | 'tiktok' | 'twitter'
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
      case 'youtube':
        return {
          icon: Globe, // YouTube 아이콘 대신 임시로 Globe 사용
          label: 'YouTube',
          color: isConnected ? 'bg-gradient-to-r from-red-500 to-red-600' : 'bg-gray-100',
          textColor: isConnected ? 'text-white' : 'text-gray-600'
        }
      case 'tiktok':
        return {
          icon: Globe, // TikTok 아이콘 대신 임시로 Globe 사용
          label: 'TikTok',
          color: isConnected ? 'bg-gradient-to-r from-black to-gray-800' : 'bg-gray-100',
          textColor: isConnected ? 'text-white' : 'text-gray-600'
        }
      case 'twitter':
        return {
          icon: Globe, // Twitter 아이콘 대신 임시로 Globe 사용
          label: 'Twitter',
          color: isConnected ? 'bg-gradient-to-r from-blue-400 to-blue-500' : 'bg-gray-100',
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