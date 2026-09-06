/*
FuCadUp Installer Language File
Language: Polish
*/

!insertmacro LANGFILE_EXT "Polish"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Zainstalowane dla bieżącego użytkownika)"

${LangFileString} TEXT_WELCOME "Kreator przeprowadzi Ciebie przez proces instalacji FuCadUp$\'a.$\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Kompilowanie skryptów Python..."

${LangFileString} TEXT_FINISH_DESKTOP "Utwórz skrót na pulpicie"
${LangFileString} TEXT_FINISH_WEBSITE "Odwiedź github.com/otherworld-dev/FuCadUp by poznać wiadomości i wskazówki lub skorzystać ze wsparcia"

#${LangFileString} FileTypeTitle "Dokument FuCadUp"

#${LangFileString} SecAllUsersTitle "Instalacja dla wszystkich użytkowników?"
${LangFileString} SecFileAssocTitle "Skojarzenie plików .FCStd"
${LangFileString} SecDesktopTitle "Ikona na pulpicie"

${LangFileString} SecCoreDescription "Pliki FuCadUp$\'a."
#${LangFileString} SecAllUsersDescription "Instalacja dla wszystkich użytkowników lub tylko dla bieżącego użytkownika."
${LangFileString} SecFileAssocDescription "Skojarzenie FuCadUp-a z plikami o rozszerzeniu .FCStd."
${LangFileString} SecDesktopDescription "Ikona FuCadUp$\'a na pulpicie."
#${LangFileString} SecDictionaries "Słowniki"
#${LangFileString} SecDictionariesDescription "Słowniki sprawdzania pisowni, które mogą zostać pobrane i zainstalowane."

#${LangFileString} PathName 'Ścieżka do pliku $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'Plik $\"xxx.exe$\" nie znajduje się w podanej ścieżce.'

#${LangFileString} DictionariesFailed 'Pobranie słownika dla języka $\"$R3$\" nie powiodło się.'

#${LangFileString} ConfigInfo "Dalsza konfiguracja FuCadUp$\'a chwilę potrwa."

#${LangFileString} RunConfigureFailed "Niedana próba wykonania skryptu konfiguracyjnego"
${LangFileString} InstallRunning "Instalator jest już uruchomiony!"
${LangFileString} AlreadyInstalled "FuCadUp ${APP_SERIES_KEY2} jest już zainstalowany!$\r$\n\
				Dou you nevertheles want to install FuCadUp over the existing version?"
${LangFileString} NewerInstalled "Próbujesz zainstalować starszą wersję FuCadUp, niż ta która jest już zainstalowana.$\r$\n\
				  Jeżeli naprawdę chcesz tego dokonać, musisz wpierw odinstalować FuCadUp $OldVersionNumber."

#${LangFileString} FinishPageMessage "Gratulacje! FuCadUp został pomyślnie zainstalowany.$\r$\n\
#					$\r$\n\
#					(Pierwsze uruchomienie może potrwać kilka sekund.)"
${LangFileString} FinishPageRun "Uruchom FuCadUp"

${LangFileString} UnNotInRegistryLabel "Nie można znaleźć FuCadUp$\'a w rejestrze.$\r$\n\
					Skróty na pulpicie i w menu Start nie zostaną usunięte."
${LangFileString} UnInstallRunning "Musisz najpierw zamknąć FuCadUp$\'a!"
${LangFileString} UnNotAdminLabel "Musisz posiadać prawa administratora do deinstalacji programu FuCadUp."
${LangFileString} UnReallyRemoveLabel "Czy na pewno chcesz usunąć FuCadUp$\'a i wszystkie jego komponenty?"
${LangFileString} UnFuCadUpPreferencesTitle 'Preferencje użytkownika FuCadUp$\'a'

#${LangFileString} SecUnProgDescription "Deinstalacja xxx."
${LangFileString} SecUnPreferencesDescription 'Usuwa folder konfiguracji FuCadUp$\'a$\r$\n\
						$\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						wszystkim użytkownikom.'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUps user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons.$\r$\n\
						Do you agree with this?'
${LangFileString} SecUnProgramFilesDescription "Deinstalacja FuCadUp i wszystkich jego komponentów."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
