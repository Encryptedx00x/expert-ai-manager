param(
    [Parameter(Mandatory = $true)]
    [long]$WindowHandle,
    [string]$RequestId = '',
    [string]$ExpectedConversationUrl = '',
    [switch]$InvokeSend
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
if (-not $root) { throw 'ChatGPT window not found' }

$editCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Edit
)
$editControls = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $editCond)
$composerMatches = @()
$conversationUrl = ''
foreach ($control in $editControls) {
    $name = $control.Current.Name
    if ($name -in @('Address and search bar', 'Barra de endereço e pesquisa')) {
        $addressPattern = $null
        if ($control.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$addressPattern)) {
            $candidate = [string]$addressPattern.Current.Value
            if ($candidate -match '^https://(?:www\.)?chatgpt\.com/(?:[^?#]*/)?c/[0-9a-f-]+(?:[?#].*)?$') {
                $conversationUrl = ([uri]$candidate).GetLeftPart([System.UriPartial]::Path).TrimEnd('/')
            }
        }
    }
    if ($name -in @('Pergunte ao ChatGPT', 'Ask anything', 'Message ChatGPT')) {
        $composerMatches += $control
    }
}
if ($composerMatches.Count -ne 1) {
    throw "Expected exactly one ChatGPT composer; found $($composerMatches.Count)"
}

$composer = $composerMatches[0]
$e = $composer.Current
$b = $e.BoundingRectangle
if ($b.IsEmpty -or $b.Width -lt 100 -or $b.Height -lt 20) {
    throw 'ChatGPT composer not visible or too small'
}

$valueObj = $null
$editorText = ''
if ($composer.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern, [ref]$valueObj)) {
    $editorText = [string]$valueObj.Current.Value
}
$hasRequestId = (-not $RequestId) -or $editorText.Contains($RequestId)
# UI Automation may return the placeholder as the Edit.Value even when empty.
$normalizedText = $editorText.Trim()
$placeholders = @('Pergunte ao ChatGPT', 'Ask anything', 'Message ChatGPT')
$effectiveLength = if ($normalizedText -in $placeholders) { 0 } else { $editorText.Length }

$buttonCond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::Button
)
$buttons = $root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $buttonCond)
$stopButtons = @()
$sendButtons = @()
foreach ($button in $buttons) {
    $c = $button.Current
    $r = $c.BoundingRectangle
    if ($r.IsEmpty -or -not $c.IsEnabled) { continue }
    # The action button is directly to the right of the message composer.
    if ($r.Y -lt ($b.Y - 35) -or $r.Y -gt ($b.Y + $b.Height + 35)) { continue }
    if ($r.X -lt ($b.X + $b.Width - 10) -or $r.X -gt ($b.X + $b.Width + 150)) { continue }
    if ($c.Name -in @('Parar', 'Stop', 'Stop generating')) { $stopButtons += $button }
    if ($c.Name -in @('Enviar', 'Enviar mensagem', 'Send', 'Send message')) { $sendButtons += $button }
}

$generating = $stopButtons.Count -gt 0
$sent = $false
if ($InvokeSend) {
    if ($ExpectedConversationUrl -and $conversationUrl -ne $ExpectedConversationUrl) {
        throw 'ChatGPT conversation address changed. Refusing to send.'
    }
    if (-not $RequestId -or -not $hasRequestId) {
        throw 'Requested id is missing from the composer. Refusing to click.'
    }
    if ($generating) { throw 'ChatGPT still generating. Cannot submit.' }
    if ($sendButtons.Count -ne 1) {
        throw "Expected one enabled Send button; found $($sendButtons.Count)"
    }
    $action = $sendButtons[0].GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $action.Invoke()
    $sent = $true
}

[pscustomobject]@{
    x = [math]::Round($b.X)
    y = [math]::Round($b.Y)
    width = [math]::Round($b.Width)
    height = [math]::Round($b.Height)
    name = $e.Name
    conversation_url = $conversationUrl
    text_length = $effectiveLength
    request_id_present = [bool]$hasRequestId
    generating = [bool]$generating
    send_button_enabled = [bool]($sendButtons.Count -eq 1)
    invoked = [bool]$sent
} | ConvertTo-Json -Compress
