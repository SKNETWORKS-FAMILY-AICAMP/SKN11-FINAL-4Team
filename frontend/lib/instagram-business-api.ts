// Instagram API with Instagram Login 관리 서비스
interface InstagramUser {
  id: string;
  username: string;
  account_type: 'BUSINESS' | 'CREATOR' | 'PERSONAL';
  media_count: number;
  name?: string;
  biography?: string;
  website?: string;
  profile_picture_url?: string;
  followers_count?: number;
  follows_count?: number;
}

interface InstagramMedia {
  id: string;
  caption?: string;
  media_type: 'IMAGE' | 'VIDEO' | 'CAROUSEL_ALBUM';
  media_url: string;
  permalink: string;
  timestamp: string;
  like_count?: number;
  comments_count?: number;
  thumbnail_url?: string;
}

interface InstagramInsights {
  name: string;
  period: string;
  values: Array<{
    value: number;
    end_time: string;
  }>;
  title: string;
  description: string;
}

interface InstagramComment {
  id: string;
  text: string;
  timestamp: string;
  username: string;
  like_count?: number;
  replies?: {
    data: InstagramComment[];
  };
}

export class InstagramAPIService {
  private accessToken: string;
  private baseUrl = 'https://graph.instagram.com/v18.0';

  constructor(accessToken: string) {
    this.accessToken = accessToken;
  }

  // Instagram 사용자 정보 조회
  async getUserInfo(userId: string = 'me'): Promise<InstagramUser> {
    const fields = 'id,username,account_type,media_count,name,biography,website,profile_picture_url,followers_count,follows_count';
    const response = await fetch(
      `${this.baseUrl}/${userId}?fields=${fields}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch user info: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 미디어 목록 조회
  async getMedia(userId: string = 'me', limit: number = 25): Promise<InstagramMedia[]> {
    const fields = 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count,thumbnail_url';
    const response = await fetch(
      `${this.baseUrl}/${userId}/media?fields=${fields}&limit=${limit}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch media: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  // 특정 미디어 상세 정보 조회
  async getMediaDetails(mediaId: string): Promise<InstagramMedia> {
    const fields = 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count,thumbnail_url';
    const response = await fetch(
      `${this.baseUrl}/${mediaId}?fields=${fields}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch media details: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 미디어 댓글 조회
  async getMediaComments(mediaId: string): Promise<InstagramComment[]> {
    const fields = 'id,text,timestamp,username,like_count,replies{id,text,timestamp,username,like_count}';
    const response = await fetch(
      `${this.baseUrl}/${mediaId}/comments?fields=${fields}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch comments: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  // 댓글에 답글 달기
  async replyToComment(commentId: string, message: string): Promise<{ id: string }> {
    const response = await fetch(`${this.baseUrl}/${commentId}/replies`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: message,
        access_token: this.accessToken
      })
    });
    
    if (!response.ok) {
      throw new Error(`Failed to reply to comment: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 계정 인사이트 조회 (Business/Creator 계정만)
  async getAccountInsights(userId: string = 'me', metrics: string[] = ['impressions', 'reach', 'profile_views']): Promise<InstagramInsights[]> {
    const metricsStr = metrics.join(',');
    const response = await fetch(
      `${this.baseUrl}/${userId}/insights?metric=${metricsStr}&period=day&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch account insights: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  // 미디어 인사이트 조회
  async getMediaInsights(mediaId: string, metrics: string[] = ['impressions', 'reach', 'engagement']): Promise<InstagramInsights[]> {
    const metricsStr = metrics.join(',');
    const response = await fetch(
      `${this.baseUrl}/${mediaId}/insights?metric=${metricsStr}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch media insights: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  // 컨테이너 생성 (게시물 업로드 준비)
  async createMediaContainer(userId: string = 'me', imageUrl: string, caption?: string): Promise<{ id: string }> {
    const body: any = {
      image_url: imageUrl,
      access_token: this.accessToken
    };
    
    if (caption) {
      body.caption = caption;
    }
    
    const response = await fetch(`${this.baseUrl}/${userId}/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body)
    });
    
    if (!response.ok) {
      throw new Error(`Failed to create media container: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 미디어 게시
  async publishMedia(userId: string = 'me', creationId: string): Promise<{ id: string }> {
    const response = await fetch(`${this.baseUrl}/${userId}/media_publish`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        creation_id: creationId,
        access_token: this.accessToken
      })
    });
    
    if (!response.ok) {
      throw new Error(`Failed to publish media: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 해시태그 검색
  async searchHashtags(hashtag: string): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/ig_hashtag_search?user_id=${this.accessToken}&q=${hashtag}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to search hashtags: ${response.statusText}`);
    }
    
    return await response.json();
  }

  // 멘션된 미디어 조회
  async getMentionedMedia(accountId: string): Promise<InstagramMedia[]> {
    const fields = 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count';
    const response = await fetch(
      `${this.baseUrl}/${accountId}?fields=mentioned_media.limit(25){${fields}}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch mentioned media: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.mentioned_media?.data || [];
  }

  // 스토리 조회
  async getStories(accountId: string): Promise<InstagramMedia[]> {
    const fields = 'id,media_type,media_url,permalink,timestamp';
    const response = await fetch(
      `${this.baseUrl}/${accountId}/stories?fields=${fields}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch stories: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.data;
  }

  // 계정 태그된 미디어 조회
  async getTaggedMedia(accountId: string): Promise<InstagramMedia[]> {
    const fields = 'id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count';
    const response = await fetch(
      `${this.baseUrl}/${accountId}?fields=tagged_media.limit(25){${fields}}&access_token=${this.accessToken}`
    );
    
    if (!response.ok) {
      throw new Error(`Failed to fetch tagged media: ${response.statusText}`);
    }
    
    const data = await response.json();
    return data.tagged_media?.data || [];
  }
}