/**
 * 시간대 변환 유틸리티
 */

/**
 * KST 시간을 포맷팅 (백엔드에서 이미 KST로 저장됨)
 * @param kstTime KST 시간 문자열 또는 Date 객체
 * @returns 포맷팅된 한국 시간 문자열
 */
export function convertUTCToKST(kstTime: string | Date): string {
    try {
        const date = typeof kstTime === 'string' ? new Date(kstTime) : kstTime;

        // 백엔드에서 이미 KST로 저장되므로 변환 없이 포맷팅만
        return date.toLocaleString('ko-KR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    } catch (error) {
        return kstTime.toString();
    }
}

/**
 * 한국 시간을 UTC 시간으로 변환
 * @param kstTime 한국 시간 문자열
 * @returns UTC 시간 문자열
 */
export function convertKSTToUTC(kstTime: string): string {
    try {
        // 한국 시간을 Date 객체로 변환
        const date = new Date(kstTime + ' GMT+9');

        // UTC로 변환
        return date.toISOString();
    } catch (error) {
        return kstTime;
    }
}

/**
 * 현재 한국 시간 가져오기
 * @returns 한국 시간 문자열
 */
export function getCurrentKST(): string {
    const now = new Date();
    return convertUTCToKST(now);
}

/**
 * 시간을 상대적 표현으로 변환 (예: "3분 전", "1시간 전")
 * @param time 시간 문자열 또는 Date 객체
 * @returns 상대적 시간 표현
 */
export function getRelativeTime(time: string | Date): string {
    try {
        const date = typeof time === 'string' ? new Date(time) : time;
        const now = new Date();
        const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

        if (diffInSeconds < 60) {
            return '방금 전';
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return `${minutes}분 전`;
        } else if (diffInSeconds < 86400) {
            const hours = Math.floor(diffInSeconds / 3600);
            return `${hours}시간 전`;
        } else if (diffInSeconds < 2592000) {
            const days = Math.floor(diffInSeconds / 86400);
            return `${days}일 전`;
        } else {
            const months = Math.floor(diffInSeconds / 2592000);
            return `${months}개월 전`;
        }
    } catch (error) {
        return '알 수 없음';
    }
}

/**
 * 날짜를 한국어 형식으로 포맷팅 (백엔드에서 이미 KST로 저장됨)
 * @param time 시간 문자열 또는 Date 객체
 * @returns 한국어 형식의 날짜 문자열
 */
export function formatDateKorean(time: string | Date): string {
    try {
        const date = typeof time === 'string' ? new Date(time) : time;

        // 백엔드에서 이미 KST로 저장되므로 변환 없이 포맷팅만
        const year = date.getFullYear();
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');

        return `${year}년 ${month}월 ${day}일 ${hours}:${minutes}`;
    } catch (error) {
        return time.toString();
    }
} 