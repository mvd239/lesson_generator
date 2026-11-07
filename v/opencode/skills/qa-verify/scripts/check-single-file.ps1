param(
    [string]$Path = "index.html"
)

# Статическая проверка одностраничной игры для Windows PowerShell 5.1+.
# Использование:
#   powershell -NoProfile -ExecutionPolicy Bypass -File check-single-file.ps1 path\to\index.html

$ErrorActionPreference = "Stop"

try {
    [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
    $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
} catch {
    # Консоль может не поддерживать UTF-8 — проверка продолжит работать.
}

$script:results = New-Object System.Collections.Generic.List[object]

function Add-Result {
    param([string]$Level, [string]$Message)
    $script:results.Add([pscustomobject]@{ Level = $Level; Message = $Message })
}

function Need {
    param([bool]$Condition, [string]$OkMessage, [string]$FailMessage)
    if ($Condition) { Add-Result "OK" $OkMessage }
    else { Add-Result "FAIL" $FailMessage }
}

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Host "[FAIL] Файл не найден: $Path"
    exit 1
}

$item = Get-Item -LiteralPath $Path
$src = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
$sizeKb = [math]::Round($item.Length / 1KB, 1)

Add-Result "OK" ("Файл найден: {0} ({1} KB)" -f $Path, $sizeKb)

# ---------- Каркас документа ----------

Need ($src -match '<!doctype\s+html>') "Есть <!DOCTYPE html>" "Нет <!DOCTYPE html>"
Need ($src -match '<html[^>]+lang\s*=\s*["'']ru["'']') "Указан lang=`"ru`"" "Не указан lang=`"ru`""
Need (($src -match '<meta[^>]+name\s*=\s*["'']viewport["'']') -and ($src -match 'width\s*=\s*device-width')) "Есть meta viewport" "Нет meta viewport с width=device-width"
Need ($src -match '<title>[^<]{3,}</title>') "Есть непустой <title>" "Нет непустого <title>"

# ---------- Внешние зависимости ----------

Need (-not ($src -match '<script\b[^>]*\bsrc\s*=')) "Нет внешних <script src>" "Найден внешний <script src> — библиотеки запрещены"
Need (-not ($src -match '\bimport\s*(?:\(|[^;]*from\s*)["'']https?:')) "Нет импортов по URL" "Найден import по URL"

$hosts = @()
foreach ($m in [regex]::Matches($src, 'https?://([\w.-]+)')) {
    $hosts += $m.Groups[1].Value.ToLowerInvariant()
}
$hosts = $hosts | Sort-Object -Unique
$allowedHosts = @("fonts.googleapis.com", "fonts.gstatic.com", "www.w3.org", "w3.org")
$badHosts = @($hosts | Where-Object { $allowedHosts -notcontains $_ })
if ($badHosts.Count -eq 0) {
    Add-Result "OK" "Внешние URL только Google Fonts / SVG namespace"
} else {
    Add-Result "FAIL" ("Подозрительные внешние URL: " + ($badHosts -join ", "))
}

$fontLink = ($src -match 'fonts\.googleapis\.com/css2\?[^"'']*family=Comic\+Neue') -or ($src -match 'fonts\.googleapis\.com/css\?[^"'']*family=Comic\+Neue')
Need $fontLink "Подключён Comic Neue через Google Fonts" "Не найден Google Fonts с Comic Neue"
Need ($src -match 'display\s*=\s*swap') "Шрифт с display=swap" "У шрифта нет display=swap"
Need (($src -match 'Comic\s+Neue') -and ($src -match 'Comic Sans MS|Segoe UI|sans-serif')) "Есть fallback-стек шрифтов" "Нет fallback-стека для шрифта"

# ---------- Перетаскивание и сенсор ----------

Need ($src -match 'pointerdown|touchstart') "Обработка Pointer/Touch Events есть" "Нет обработки pointerdown/touchstart"
Need ($src -match 'touch-action\s*:\s*none') "touch-action: none задан" "Нет touch-action: none"
Need ($src -match 'elementFromPoint') "Hit-test через elementFromPoint" "Нет elementFromPoint для определения зоны"
Need (-not ($src -match 'draggable\s*=\s*["'']true["'']')) "HTML5 Drag-and-Drop не используется" "Найден draggable=`"true`" — используйте Pointer/Touch"
Need ($src -match 'pointermove|touchmove') "Есть обработчик движения" "Нет pointermove/touchmove"
Need ($src -match 'pointerup|touchend') "Есть обработчик отпускания" "Нет pointerup/touchend"

# ---------- Игровая логика ----------

$dropzones = ([regex]::Matches($src, 'data-dropzone')).Count
$answers = ([regex]::Matches($src, 'data-answer')).Count
if ($dropzones -ge 6) { Add-Result "OK" ("Зон ответа в разметке: " + $dropzones) }
else { Add-Result "WARN" ("В исходнике " + $dropzones + " вхождений data-dropzone; проверь вручную, что зон 6") }
if ($answers -ge 6) { Add-Result "OK" ("Ключей ответов: " + $answers) }
else { Add-Result "WARN" ("В исходнике " + $answers + " вхождений data-answer; проверь вручную, что пар 6") }

Need ($src -match 'role\s*=\s*["'']dialog["'']') "Финальное окно с role=`"dialog`"" "Нет role=`"dialog`" у финального окна"
Need ($src -match 'location\.reload\s*\(|reset|restart') "Есть перезапуск игры" "Не найден перезапуск (location.reload или reset)"
Need ($src -match 'aria-live\s*=\s*["''](polite|assertive)["'']') "Есть aria-live для обратной связи" "Нет aria-live для объявления результата"
Need ($src -match ':focus-visible') "Есть стиль :focus-visible" "Нет :focus-visible"

if ($src -match 'prefers-reduced-motion') { Add-Result "OK" "Учтён prefers-reduced-motion" }
else { Add-Result "WARN" "Нет prefers-reduced-motion — анимацию нельзя отключить" }

if ($src -match 'overflow-wrap\s*:\s*(anywhere|break-word)') { Add-Result "OK" "Длинные термины переносятся" }
else { Add-Result "WARN" "Нет overflow-wrap — длинный термин может вылезти за карточку" }

# ---------- Гигиена ----------

if ($src -match 'console\.log\s*\(') { Add-Result "WARN" "В коде остался console.log — уберите отладку" }
else { Add-Result "OK" "Отладочных console.log нет" }

if ($sizeKb -lt 12) { Add-Result "WARN" "Файл меньше 12 KB — похоже, часть требований не реализована" }
if ($sizeKb -gt 350) { Add-Result "WARN" "Файл больше 350 KB — проверьте, нет ли лишних данных" }

# ---------- Вывод ----------

foreach ($r in $script:results) {
    Write-Host ("[{0}] {1}" -f $r.Level, $r.Message)
}

$fails = @($script:results | Where-Object { $_.Level -eq "FAIL" }).Count
$warns = @($script:results | Where-Object { $_.Level -eq "WARN" }).Count
$oks = @($script:results | Where-Object { $_.Level -eq "OK" }).Count

Write-Host ""
Write-Host ("Итог: {0} FAIL, {1} WARN, {2} OK" -f $fails, $warns, $oks)
if ($fails -eq 0) {
    Write-Host "Статические проверки пройдены. Осталось ручное тестирование по чек-листу qa-verify."
    exit 0
} else {
    Write-Host "Есть блокирующие ошибки. Исправьте их и запустите проверку снова."
    exit 1
}
