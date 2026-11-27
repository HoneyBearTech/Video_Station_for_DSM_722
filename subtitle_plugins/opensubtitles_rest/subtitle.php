<?php
/** REST adapter for the existing Video Station 3.1.0 subtitle command contract. */
class SubtitleRestClient
{
    private $key;
    private $token = '';
    private $base = 'https://api.opensubtitles.com/api/v1';
    private $transport;
    private static $apiHosts = array('api.opensubtitles.com', 'vip-api.opensubtitles.com');
    private static $languages = array(
        'eng'=>'en', 'fre'=>'fr', 'fra'=>'fr', 'ger'=>'de', 'deu'=>'de',
        'spa'=>'es', 'ita'=>'it', 'dut'=>'nl', 'nld'=>'nl', 'por'=>'pt-pt',
        'pob'=>'pt-br', 'chi'=>'zh-cn', 'zho'=>'zh-cn', 'jpn'=>'ja', 'kor'=>'ko',
        'rus'=>'ru', 'pol'=>'pl', 'cze'=>'cs', 'ces'=>'cs', 'dan'=>'da',
        'swe'=>'sv', 'nor'=>'no', 'fin'=>'fi', 'hun'=>'hu', 'gre'=>'el',
        'ell'=>'el', 'tur'=>'tr', 'ara'=>'ar', 'heb'=>'he', 'tha'=>'th',
        'vie'=>'vi', 'ind'=>'id', 'rum'=>'ro', 'ron'=>'ro', 'ukr'=>'uk',
        'bul'=>'bg', 'hrv'=>'hr', 'srp'=>'sr', 'slv'=>'sl', 'slo'=>'sk',
        'slk'=>'sk', 'est'=>'et', 'lav'=>'lv', 'lit'=>'lt', 'hin'=>'hi'
    );

    public function __construct($key, $transport = null)
    {
        $this->key = trim($key);
        if ($this->key === '' || preg_match('/[\r\n]/', $this->key)) {
            throw new RuntimeException('API key is missing or invalid');
        }
        $this->transport = $transport;
    }

    private static function checkUrl($url, $api)
    {
        $parts = parse_url($url);
        $host = isset($parts['host']) ? strtolower($parts['host']) : '';
        $allowed = $api ? in_array($host, self::$apiHosts, true)
            : ($host === 'opensubtitles.com' || substr($host, -18) === '.opensubtitles.com');
        if (!$parts || ($parts['scheme'] ?? '') !== 'https' || !$allowed ||
                isset($parts['user']) || isset($parts['pass']) ||
                (isset($parts['port']) && $parts['port'] !== 443)) {
            throw new RuntimeException('Untrusted service URL');
        }
    }

    private function transfer($url, $method, $headers, $body, $api)
    {
        for ($redirect = 0; $redirect < 4; $redirect++) {
            self::checkUrl($url, $api);
            if ($this->transport !== null) {
                $response = call_user_func($this->transport, $url, $method, $headers, $body);
            } else {
                if (!function_exists('curl_init')) {
                    throw new RuntimeException('The PHP cURL extension is required');
                }
                $handle = curl_init($url);
                $content = '';
                $responseHeaders = array();
                curl_setopt_array($handle, array(
                    CURLOPT_CUSTOMREQUEST => $method,
                    CURLOPT_HTTPHEADER => $headers,
                    CURLOPT_CONNECTTIMEOUT => 15,
                    CURLOPT_TIMEOUT => 40,
                    CURLOPT_SSL_VERIFYHOST => 2,
                    CURLOPT_SSL_VERIFYPEER => true,
                    CURLOPT_FOLLOWLOCATION => false,
                    CURLOPT_PROTOCOLS => CURLPROTO_HTTPS,
                    CURLOPT_WRITEFUNCTION => function ($handle, $chunk) use (&$content) {
                        if (strlen($content) + strlen($chunk) > 8 * 1024 * 1024) {
                            return 0;
                        }
                        $content .= $chunk;
                        return strlen($chunk);
                    },
                    CURLOPT_HEADERFUNCTION => function ($handle, $line) use (&$responseHeaders) {
                        $split = explode(':', $line, 2);
                        if (count($split) === 2) {
                            $responseHeaders[strtolower(trim($split[0]))] = trim($split[1]);
                        }
                        return strlen($line);
                    }
                ));
                if ($body !== null) {
                    curl_setopt($handle, CURLOPT_POSTFIELDS, $body);
                }
                $ok = curl_exec($handle);
                $status = curl_getinfo($handle, CURLINFO_HTTP_CODE);
                curl_close($handle);
                if ($ok === false) {
                    throw new RuntimeException('Subtitle service transfer failed');
                }
                $response = array($status, $content, $responseHeaders);
            }
            list($status, $content, $responseHeaders) = $response;
            if (strlen($content) > 8 * 1024 * 1024) {
                throw new RuntimeException('Subtitle service response is too large');
            }
            if (in_array($status, array(301, 302, 303, 307, 308), true)) {
                if ($method !== 'GET' || empty($responseHeaders['location'])) {
                    throw new RuntimeException('Unexpected service redirect');
                }
                $location = $responseHeaders['location'];
                if (substr($location, 0, 1) === '/' && substr($location, 0, 2) !== '//') {
                    $parts = parse_url($url);
                    $location = 'https://' . $parts['host'] . $location;
                }
                $url = $location;
                continue;
            }
            if ($status < 200 || $status >= 300) {
                // Do not echo server response bodies, which may contain account details.
                throw new RuntimeException('Subtitle service returned HTTP ' . (int)$status);
            }
            return $content;
        }
        throw new RuntimeException('Too many service redirects');
    }

    private function request($path, $body = null)
    {
        $headers = array('Api-Key: ' . $this->key, 'User-Agent: VideoStation-Subtitle-REST v1.0',
                         'Accept: application/json');
        if ($this->token !== '') {
            $headers[] = 'Authorization: Bearer ' . $this->token;
        }
        if ($body !== null) {
            $headers[] = 'Content-Type: application/json';
        }
        $raw = $this->transfer($this->base . $path, $body === null ? 'GET' : 'POST',
            $headers, $body === null ? null : json_encode($body), true);
        $decoded = json_decode($raw, true);
        if (!is_array($decoded)) {
            throw new RuntimeException('Invalid subtitle service response');
        }
        return $decoded;
    }

    public function login($username, $password)
    {
        if ($username === '' || $password === '') {
            throw new RuntimeException('OpenSubtitles.com username and password are required');
        }
        $result = $this->request('/login', array('username'=>$username, 'password'=>$password));
        if (empty($result['token']) || !is_string($result['token']) || preg_match('/[\r\n]/', $result['token'])) {
            throw new RuntimeException('Subtitle login failed');
        }
        $host = $result['base_url'] ?? 'api.opensubtitles.com';
        // Only a bare host name: no scheme, port, user, path, query or fragment.
        if (!is_string($host) || !in_array(strtolower($host), self::$apiHosts, true)) {
            throw new RuntimeException('Untrusted service URL');
        }
        $this->base = 'https://' . $host . '/api/v1';
        $this->token = $result['token'];
    }

    public static function movieHash($path)
    {
        $size = filesize($path);
        if ($size === false || $size < 131072 || PHP_INT_SIZE < 8) {
            return '';
        }
        $stream = fopen($path, 'rb');
        if ($stream === false) {
            throw new RuntimeException('Cannot read video file');
        }
        $low = $size & 0xffffffff;
        $high = ($size >> 32) & 0xffffffff;
        try {
            foreach (array(0, $size - 65536) as $offset) {
                if (fseek($stream, $offset) !== 0) {
                    throw new RuntimeException('Cannot seek video file');
                }
                $data = fread($stream, 65536);
                if (strlen($data) !== 65536) {
                    throw new RuntimeException('Cannot hash video file');
                }
                for ($i = 0; $i < 65536; $i += 8) {
                    $word = unpack('Vlow/Vhigh', substr($data, $i, 8));
                    $sum = $low + $word['low'];
                    $high = ($high + $word['high'] + ($sum > 0xffffffff ? 1 : 0)) & 0xffffffff;
                    $low = $sum & 0xffffffff;
                }
            }
        } finally {
            fclose($stream);
        }
        return sprintf('%08x%08x', $high, $low);
    }

    public static function subtitlePath($path, $id)
    {
        if (!preg_match('/^rest-([a-z]{2,3}(?:-[a-z]{2})?)-([1-9][0-9]{0,9})$/D', $id, $match)) {
            throw new RuntimeException('Invalid subtitle selection');
        }
        if (strlen($match[2]) === 10 && strcmp($match[2], '2147483647') > 0) {
            throw new RuntimeException('Subtitle file identifier is out of range');
        }
        $video = realpath($path);
        if ($video === false || !is_file($video)) {
            throw new RuntimeException('Video file is unavailable');
        }
        $prefix = pathinfo($video, PATHINFO_FILENAME);
        $legacyLanguage = array_search($match[1], self::$languages, true);
        if ($legacyLanguage === false) {
            $legacyLanguage = 'und';
        }
        // The older playback library recognizes the language immediately before .srt.
        return dirname($video) . '/' . $prefix . '.rest-' . $match[2] . '.' . $legacyLanguage . '.srt';
    }

    public function search($options)
    {
        $path = $options['path'] ?? '';
        if ($path !== '' && !is_file($path)) {
            throw new RuntimeException('A readable video path is required');
        }
        if ($path === '' && (empty($options['hash']) || empty($options['size']))) {
            throw new RuntimeException('Provide a video path or both movie hash and size');
        }
        $requested = explode(',', strtolower($options['lang'] ?? 'eng'));
        $languageMap = array();
        foreach ($requested as $language) {
            $code = self::$languages[$language] ?? $language;
            if (!preg_match('/^[a-z]{2}(?:-[a-z]{2})?$/D', $code)) {
                throw new RuntimeException('Unsupported subtitle language');
            }
            $languageMap[$code] = $language;
        }
        $params = array('languages'=>implode(',', array_keys($languageMap)));
        if ($path !== '') {
            $params['query'] = strtolower(pathinfo($path, PATHINFO_FILENAME));
        }
        $hash = $options['hash'] ?? self::movieHash($path);
        if ($hash !== '') {
            if (!preg_match('/^[a-f0-9]{16}$/Di', $hash)) {
                throw new RuntimeException('Invalid movie hash');
            }
            $params['moviehash'] = strtolower($hash);
        }
        ksort($params);
        $result = $this->request('/subtitles?' . http_build_query($params, '', '&', PHP_QUERY_RFC3986));
        if (!isset($result['data']) || !is_array($result['data'])) {
            throw new RuntimeException('Invalid subtitle search response');
        }
        $limit = max(1, min(100, (int)($options['limit'] ?? 10)));
        $items = array();
        foreach ($result['data'] as $record) {
            $attributes = $record['attributes'] ?? array();
            $language = strtolower($attributes['language'] ?? '');
            if (!isset($languageMap[$language])) {
                continue;
            }
            foreach (($attributes['files'] ?? array()) as $file) {
                // The record ID identifies a subtitle group; download requires a file_id.
                $fileId = (string)($file['file_id'] ?? '');
                $id = 'rest-' . $language . '-' . $fileId;
                if (!preg_match('/^rest-[a-z]{2,3}(?:-[a-z]{2})?-[1-9][0-9]{0,9}$/D', $id) ||
                        (strlen($fileId) === 10 && strcmp($fileId, '2147483647') > 0)) {
                    throw new RuntimeException('Invalid subtitle file identifier');
                }
                $destination = $path !== '' ? self::subtitlePath($path, $id) : '';
                $exists = $destination !== '' && is_file($destination) && !is_link($destination);
                $items[] = array('id'=>$id, 'language'=>$language, 'language_id'=>$languageMap[$language],
                    'filename'=>(string)($file['file_name'] ?? $attributes['release'] ?? ''),
                    'downloaded'=>$exists, 'subtitle_id'=>$exists ? $destination : '');
                if (count($items) >= $limit) {
                    break 2;
                }
            }
        }
        return array('items'=>$items, 'total'=>count($items));
    }

    public function download($path, $id)
    {
        $destination = self::subtitlePath($path, $id);
        if (file_exists($destination) || is_link($destination)) {
            if (!is_file($destination) || is_link($destination)) {
                throw new RuntimeException('Subtitle destination is unsafe');
            }
            return array('id'=>$destination);
        }
        preg_match('/-([0-9]+)$/D', $id, $match);
        $result = $this->request('/download', array('file_id'=>(int)$match[1], 'sub_format'=>'srt'));
        if (empty($result['link']) || !is_string($result['link'])) {
            throw new RuntimeException('Subtitle download is unavailable');
        }
        // File hosts receive no account token, API key, or password.
        $contents = $this->transfer($result['link'], 'GET', array('User-Agent: VideoStation-Subtitle-REST v1.0'), null, false);
        if ($contents === '') {
            throw new RuntimeException('Subtitle download is empty');
        }
        $temporary = tempnam(dirname($destination), '.subtitle-');
        if ($temporary === false) {
            throw new RuntimeException('Cannot create subtitle file');
        }
        try {
            if (file_put_contents($temporary, $contents) !== strlen($contents) || !chmod($temporary, 0644)) {
                throw new RuntimeException('Cannot write subtitle file');
            }
            // An exclusive hard link publishes the completed file without overwriting a race winner.
            if (!@link($temporary, $destination)) {
                throw new RuntimeException('Subtitle destination already exists or is unwritable');
            }
        } finally {
            unlink($temporary);
        }
        return array('id'=>$destination);
    }
}

function subtitleRestMain()
{
    $options = getopt('', array('action:', 'path:', 'lang:', 'id:', 'username:', 'password:', 'limit:', 'hash:', 'size:'));
    try {
        $action = $options['action'] ?? '';
        if (!in_array($action, array('search', 'download'), true)) {
            throw new RuntimeException('Use --action=search or --action=download');
        }
        $keyPath = getenv('SUBTITLE_REST_KEY_FILE') ?: __DIR__ . '/api-key';
        if (is_link($keyPath) || !is_file($keyPath) || fileowner($keyPath) !== 0 ||
                (fileperms($keyPath) & 0007) !== 0) {
            throw new RuntimeException('API key file is missing or has unsafe permissions');
        }
        $key = file_get_contents($keyPath);
        if ($key === false) {
            throw new RuntimeException('Cannot read API key file');
        }
        $client = new SubtitleRestClient($key);
        $client->login($options['username'] ?? '', $options['password'] ?? (getenv('SUBTITLE_PLUGIN_PASSWORD') ?: ''));
        if ($action === 'search') {
            $output = $client->search($options);
        } elseif ($action === 'download') {
            $output = $client->download($options['path'] ?? '', $options['id'] ?? '');
        } else {
            throw new RuntimeException('Use --action=search or --action=download');
        }
        echo json_encode($output, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n";
        return 0;
    } catch (Throwable $error) {
        fwrite(STDERR, $error->getMessage() . "\n");
        echo json_encode(array('error'=>'subtitle_service_unavailable')) . "\n";
        return 1;
    }
}

if (realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    exit(subtitleRestMain());
}
