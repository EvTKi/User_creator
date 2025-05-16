function Get-FileEncoding {
  param([string]$Path)
  $fs = [System.IO.File]::Open($Path, 'Open', 'Read')
  $bytes = New-Object byte[] 4
  $fs.Read($bytes, 0, 4) | Out-Null
  $fs.Close()
  switch -regex ($bytes -join ',') {
    '^239,187,191' { return "utf-8" }
    '^255,254,0,0' { return "utf-32" }
    '^255,254' { return "utf-16" }
    '^254,255' { return "big-endian-unicode" }
    default { return "windows-1251" }
  }
}

function Get-UserGuid {
  param ([string]$SamAccountName)
  $user = Get-ADUser -Filter "sAMAccountName -eq '$SamAccountName'"
  if ($user) {
    return $user.ObjectGUID.Guid
  }
  else {
    return $null
  }
}

# --- Выбор режима ---
$mode = Read-Host "Использовать данные из AD по логину (Y) или по CSV (N)? (y/n)"
$mode = $mode.ToLower()
if ($mode -eq 'y') {
  $adGuid = (Get-ADDomain).ObjectGUID.Guid
  Write-Host "GUID домена (adGuid) из AD: $adGuid"
}
else {
  $adGuid = Read-Host "Введите GUID домена (adGuid)"
}
$files = Get-ChildItem -Path $PWD -Filter '*.csv' | Where-Object { $_.Name -ne 'Sample.csv' }

$notFoundInAD = @()

foreach ($csv in $files) {
  $origEncoding = Get-FileEncoding $csv.FullName
  $origText = [System.IO.File]::ReadAllText($csv.FullName, [System.Text.Encoding]::GetEncoding($origEncoding))
  $tempCsv = [System.IO.Path]::GetTempFileName()
  [System.IO.File]::WriteAllText($tempCsv, $origText, [System.Text.Encoding]::GetEncoding("windows-1251"))

  $reader = New-Object System.IO.StreamReader($tempCsv, [System.Text.Encoding]::GetEncoding("windows-1251"))
  $firstLine = $reader.ReadLine()
  $reader.Close()
  if ($firstLine -match ";") { $delimiter = ";" }
  elseif ($firstLine -match ",") { $delimiter = "," }
  else { $delimiter = ";" }

  $bytes = [System.IO.File]::ReadAllBytes($tempCsv)
  $text = [System.Text.Encoding]::GetEncoding("windows-1251").GetString($bytes)
  $csvData = $text | ConvertFrom-Csv -Delimiter $delimiter

  $sysConfigXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://monitel.com/2014/schema-sysconfig#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_sysconfig">
      <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
      <md:Model.version>2020-07-09(11.6.2.35)</md:Model.version>
      <me:Model.name xmlns:me="http://monitel.com/2014/schema-cim16#">SysConfig</me:Model.name>
  </md:FullModel>`n
"@

  $energyXml = @"
<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:md="http://iec.ch/TC57/61970-552/ModelDescription/1#" xmlns:cim="http://iec.ch/TC57/2014/CIM-schema-cim16#" xmlns:cim17="http://iec.ch/TC57/2014/CIM-schema-cim17#" xmlns:me="http://monitel.com/2014/schema-cim16#" xmlns:rh="http://rushydro.ru/2015/schema-cim16#" xmlns:so="http://so-ups.ru/2015/schema-cim16#" xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <md:FullModel rdf:about="#_energy">
      <md:Model.created>$(Get-Date -Format s)Z</md:Model.created>
      <md:Model.version>ver:11.6.2.193;opt:Aggr,AMI,...</md:Model.version>
      <me:Model.name>CIM16</me:Model.name>
  </md:FullModel>`n
"@

  $updatedRows = @()

  foreach ($line in $csvData) {
    $person_guid = $line.person_guid
    $nameKey = $line.PSObject.Properties.Name | Where-Object { $_ -match "name$" }
    $name = $line.$nameKey
    if ([string]::IsNullOrWhiteSpace($name)) { continue }

    $login = $line.login
    $email = $line.email
    $mobilePhone = $line.mobilePhone
    $position = $line.position
    $OperationalAuthorities = $line.OperationalAuthorities
    $electrical_safety_level = $line.electrical_safety_level
    $roles = $line.roles
    $groups = $line.groups
    $parent_sysconfig = $line.parent_sysconfig
    $parent_energy = $line.parent_energy

    # --- Выбор способа получения GUID ---
    $markNotFound = $false
    if ($mode -eq 'y') {
      $adPersonGuid = $null
      if ($login) {
        $adPersonGuid = Get-UserGuid $login
      }
      if ($adPersonGuid) {
        $person_guid = $adPersonGuid
      }
      elseif (![string]::IsNullOrWhiteSpace($person_guid)) {
        $markNotFound = $true
      }
      else {
        $person_guid = [guid]::NewGuid().ToString()
        $markNotFound = $true
      }
    }
    else {
      if ([string]::IsNullOrWhiteSpace($person_guid)) {
        $person_guid = [guid]::NewGuid().ToString()
      }
    }

    # Собираем info о "не найденных в AD"
    if ($mode -eq 'y' -and $markNotFound) {
      $notFoundInAD += [PSCustomObject]@{
        login       = $login
        name        = $name
        person_guid = $person_guid
      }
    }

    $fio = $name -split ' '
    $fio_last = if ($fio.Length -ge 1) { $fio[0] } else { "" }
    $fio_first = if ($fio.Length -ge 2) { $fio[1] } else { "" }
    $fio_middle = if ($fio.Length -ge 3) { $fio[2] } else { "" }

    # === Подготовка блоков energy ===
    $emailBlock = ""
    if ($email) {
      $emailBlock = @"
<cim:Person.electronicAddress>
    <cim:ElectronicAddress>
      <cim:ElectronicAddress.email1>$email</cim:ElectronicAddress.email1>
    </cim:ElectronicAddress>
  </cim:Person.electronicAddress>
"@
    }
    $phoneBlock = ""
    if ($mobilePhone) {
      $phoneBlock = @"
<cim:Person.mobilePhone>
    <cim:TelephoneNumber>
      <cim:TelephoneNumber.localNumber>$mobilePhone</cim:TelephoneNumber.localNumber>
    </cim:TelephoneNumber>
  </cim:Person.mobilePhone>
"@
    }
    $positionBlock = ""
    if (![string]::IsNullOrWhiteSpace($position)) {
      $positionBlock = "<me:Person.Position rdf:resource='#_$position'/>"
    }
    $operationalBlocks = ""
    if (![string]::IsNullOrWhiteSpace($OperationalAuthorities)) {
      $uids = $OperationalAuthorities -split "!"
      foreach ($uid in $uids) {
        $trimmedUid = $uid.Trim()
        if ($trimmedUid) {
          $operationalBlocks += '    <me:Person.OperationalAuthorities rdf:resource="#_' + $trimmedUid + '" />' + "`n"
        }
      }
    }
    $electricalSafetyBlock = ""
    if (![string]::IsNullOrWhiteSpace($electrical_safety_level)) {
      $electricalSafetyBlock = '<me:Person.ElectricalSafetyLevel rdf:resource="#_' + $electrical_safety_level + '"/>' #+ "`n"
    }
    $abbreviation = $fio_last
    if ($fio_first) { $abbreviation += " " + $fio_first.Substring(0, 1) + "." }
    if ($fio_middle) { $abbreviation += $fio_middle.Substring(0, 1) + "." }
    $nmae_abbreviation_guid = [guid]::NewGuid().ToString()
    $cimNameRef = "<cim:IdentifiedObject.Names rdf:resource=""#_$nmae_abbreviation_guid"" />"
    $nameBlock = @"
<cim:Name rdf:about="#_$nmae_abbreviation_guid">
      <cim:Name.name>$abbreviation</cim:Name.name>
      <cim:Name.IdentifiedObject rdf:resource="#_$person_guid" />
      <cim:Name.NameType rdf:resource="#_00000002-0000-0000-c000-0000006d746c" />
  </cim:Name>
"@

    # === Подготовка блоков sysconfig ===
    $rolesBlocks = ""
    if (![string]::IsNullOrWhiteSpace($roles)) {
      $rolesList = $roles -split "!"
      foreach ($role in $rolesList) {
        $role = $role.Trim()
        if ($role) {
          $rolesBlocks += '<cim:Principal.Roles rdf:resource="#_' + $role + '" />'
        }
      }
    }
    $groupsBlocks = ""
    if (![string]::IsNullOrWhiteSpace($groups)) {
      $groupsList = $groups -split "!"
      foreach ($group in $groupsList) {
        $group = $group.Trim()
        if ($group) {
          $groupsBlocks += '<cim:Principal.Groups rdf:resource="#_' + $group + '" />'
        }
      }
    }

    # === Формирование energy ===
    $energyXml += @"
  <cim:Person rdf:about="#_$person_guid">
      <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
      $cimNameRef
      <me:IdentifiedObject.ParentObject rdf:resource="#_$parent_energy" />
      $emailBlock
      <cim:Person.firstName>$fio_first</cim:Person.firstName>
      <cim:Person.lastName>$fio_last</cim:Person.lastName>
      <cim:Person.mName>$fio_middle</cim:Person.mName>
      $phoneBlock
      $positionBlock
      $electricalSafetyBlock
  $operationalBlocks
  </cim:Person>
  $nameBlock`n
"@

    # === Формирование sysconfig ===
    $sysConfigXml += @"
  <cim:User rdf:about="#_$person_guid">
      <cim:IdentifiedObject.name>$name</cim:IdentifiedObject.name>
      <cim:Principal.Domain rdf:resource="#_$adGuid" />
      <cim:Principal.isEnabled>true</cim:Principal.isEnabled>
      <cim:User.login>$login</cim:User.login>
      <cim:IdentifiedObject.ParentObject rdf:resource="#_$parent_sysconfig" />
      $rolesBlocks
      $groupsBlocks 
  </cim:User>`n
"@

    $updatedRow = [PSCustomObject]@{
      person_guid             = $person_guid
      name                    = $name
      login                   = $login
      email                   = $email
      mobilePhone             = $mobilePhone
      position                = $position
      OperationalAuthorities  = $OperationalAuthorities
      electrical_safety_level = $electrical_safety_level
      roles                   = $roles
      groups                  = $groups
      parent_energy           = $parent_energy
      parent_sysconfig        = $parent_sysconfig
    }
    $updatedRows += $updatedRow
  }

  $sysConfigXml += @"
</rdf:RDF>
"@
  $energyXml += @"
</rdf:RDF>
"@

  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'sysconfig.xml'), $sysConfigXml, [System.Text.Encoding]::UTF8)
  [System.IO.File]::WriteAllText([IO.Path]::ChangeExtension($csv.FullName, 'energy.xml'), $energyXml, [System.Text.Encoding]::UTF8)

  $updatedRows | Export-Csv -Path $csv.FullName -Delimiter $delimiter -Encoding Default -NoTypeInformation
  Remove-Item $tempCsv -ErrorAction SilentlyContinue
}

# --- Запись not_ini_AD.csv, если нужно ---
if ($mode -eq 'y' -and $notFoundInAD.Count -gt 0) {
  Write-Host "`nЛогины, для которых guid не найден в AD (использовали person_guid из CSV или auto):"
  $notFoundInAD | Sort-Object -Property login | Export-Csv -Path .\not_in_AD.csv -NoTypeInformation -Delimiter ";" -Encoding UTF8
  #$notFoundInAD | Sort-Object -Property login | ForEach-Object { Write-Host "$($_.login)`t$($_.name)`t$($_.person_guid)" -ForegroundColor Yellow }
}

Write-Host "Обработка завершена. Все person_guid записаны в исходные CSV!"
