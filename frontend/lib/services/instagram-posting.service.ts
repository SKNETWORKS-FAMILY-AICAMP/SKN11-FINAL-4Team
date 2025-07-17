import apiClient from '../api';

export interface InstagramPostRequest {
    instagram_id: string;
    access_token: string;
    image_url: string;
    caption: string;
}

export interface InstagramPostResponse {
    success: boolean;
    instagram_post_id: string;
    message: string;
}

export interface InstagramPostInfo {
    id: string;
    media_type: string;
    media_url?: string;
    thumbnail_url?: string;
    permalink: string;
    timestamp: string;
    caption?: string;
    like_count?: number;
    comments_count?: number;
}

export interface InstagramPostInsight {
    id: string;
    name: string;
    value: number;
}

export interface InstagramComment {
    id: string;
    text: string;
    timestamp: string;
    username: string;
}

function toQuery(params: Record<string, any>): string {
    const esc = encodeURIComponent;
    return (
        '?' +
        Object.keys(params)
            .filter((k) => params[k] !== undefined && params[k] !== null)
            .map((k) => esc(k) + '=' + esc(params[k]))
            .join('&')
    );
}

export class InstagramPostingService {
    static async postToInstagram(
        data: InstagramPostRequest
    ): Promise<InstagramPostResponse> {
        return await apiClient.post<InstagramPostResponse>(
            '/api/v1/instagram/post',
            data
        );
    }

    static async getPostInfo(
        postId: string,
        accessToken: string,
        instagramId: string
    ): Promise<InstagramPostInfo> {
        const query = toQuery({ access_token: accessToken, instagram_id: instagramId });
        return await apiClient.get<InstagramPostInfo>(
            `/api/v1/instagram/posts/${postId}${query}`
        );
    }

    static async getUserPosts(
        accessToken: string,
        instagramId: string,
        limit: number = 10
    ): Promise<{ data: InstagramPostInfo[] }> {
        const query = toQuery({ access_token: accessToken, instagram_id: instagramId, limit });
        return await apiClient.get<{ data: InstagramPostInfo[] }>(
            `/api/v1/instagram/posts${query}`
        );
    }

    static async getPostInsights(
        postId: string,
        accessToken: string,
        instagramId: string
    ): Promise<{ data: InstagramPostInsight[] }> {
        const query = toQuery({ access_token: accessToken, instagram_id: instagramId });
        return await apiClient.get<{ data: InstagramPostInsight[] }>(
            `/api/v1/instagram/posts/${postId}/insights${query}`
        );
    }

    static async getPostComments(
        postId: string,
        accessToken: string,
        instagramId: string,
        limit: number = 10
    ): Promise<{ data: InstagramComment[] }> {
        const query = toQuery({ access_token: accessToken, instagram_id: instagramId, limit });
        return await apiClient.get<{ data: InstagramComment[] }>(
            `/api/v1/instagram/posts/${postId}/comments${query}`
        );
    }

    static async verifyPermissions(
        accessToken: string,
        instagramId: string
    ): Promise<{ is_valid: boolean; message: string }> {
        const query = toQuery({ access_token: accessToken, instagram_id: instagramId });
        return await apiClient.get<{ is_valid: boolean; message: string }>(
            `/api/v1/instagram/verify-permissions${query}`
        );
    }

    static async convertImageUrl(imageUrl: string): Promise<{ public_url: string }> {
        return await apiClient.post<{ public_url: string }>(
            '/api/v1/instagram/convert-image-url',
            { image_url: imageUrl }
        );
    }
} 