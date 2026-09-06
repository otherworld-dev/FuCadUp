/*
FuCadUp Installer Language File
Language: Slovak
*/

!insertmacro LANGFILE_EXT "Slovak"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Inštalované pre súčasného užívateľa)"

${LangFileString} TEXT_WELCOME "Tento sprievodca Vám pomáha inštalovať FuCadUp.$\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Kompilácia Python skriptov..."

${LangFileString} TEXT_FINISH_DESKTOP "Vytvoriť skratku pre pracovnú plochu"
${LangFileString} TEXT_FINISH_WEBSITE "Navštívte github.com/otherworld-dev/FuCadUp pre posledné novinky, podporu a tipy"

#${LangFileString} FileTypeTitle "FuCadUp dokument"

#${LangFileString} SecAllUsersTitle "Inštalovať pre všetkých užívateľov?"
${LangFileString} SecFileAssocTitle "Asociácie súborov"
${LangFileString} SecDesktopTitle "Ikona pracovnej plochy"

${LangFileString} SecCoreDescription "Súbory FuCadUpu."
#${LangFileString} SecAllUsersDescription "Inštalovať FuCadUp pre všetkých užívateľov alebo len pre súčasného užívateľa."
${LangFileString} SecFileAssocDescription "Súbory s rozšírením .FCStd sa automaticky otvárajú v FuCadUpe."
${LangFileString} SecDesktopDescription "Ikona FuCadUpa na pracovnej ploche."
#${LangFileString} SecDictionaries "Slovníky"
#${LangFileString} SecDictionariesDescription "Slovníky pre kontrolu pravopisu ktoré možno načítať a inštalovať."

#${LangFileString} PathName 'Cesta na súbor $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'Súbor $\"xxx.exe$\" nie je na špecifikovanej ceste.'

#${LangFileString} DictionariesFailed 'Načítanie slovníka pre jazyk $\"$R3$\" zlyhalo.'

#${LangFileString} ConfigInfo "Nasledujúca konfigurácia FuCadUpu trochu potrvá."

#${LangFileString} RunConfigureFailed "Nedal sa spustiť konfiguračný skript"
${LangFileString} InstallRunning "Inštalačný program už beží!"
${LangFileString} AlreadyInstalled "FuCadUp ${APP_SERIES_KEY2} je už inštalovaný!$\r$\n\
				Napriek tomu chcete inštalovať FuCadUp ponad existujúcu verziu?"
${LangFileString} NewerInstalled "Pokúšate sa inštalovať verziu FuCadUpu ktorá je staršia ako tá ktorá je inštalovaná.$\r$\n\
				  Keď to naozaj chcete, odinštalujte najprv existujúci FuCadUp $OldVersionNumber."

#${LangFileString} FinishPageMessage "Gratulácia! FuCadUp bol úspešne inštalovaný.$\r$\n\
#					$\r$\n\
#					(Prvý FuCadUp štart môže trvať niekoľko sekúnd.)"
${LangFileString} FinishPageRun "Spustiť FuCadUp"

${LangFileString} UnNotInRegistryLabel "Nemôžem nájsť FuCadUp v registre.$\r$\n\
					Skratky na pracovnej ploche a v štartovacom Menu sa nedajú odstrániť."
${LangFileString} UnInstallRunning "Najprv treba zavrieť FuCadUp!"
${LangFileString} UnNotAdminLabel "Pre odinštaláciu FuCadUp potrebujete administrátorské práva!"
${LangFileString} UnReallyRemoveLabel "Ste si istý, že chcete kompletne odinštalovať FuCadUp a všetky jeho súčiastky?"
${LangFileString} UnFuCadUpPreferencesTitle 'FuCadUpove užívateľské nastavenia'

#${LangFileString} SecUnProgDescription "Odinštaluje xxx."
${LangFileString} SecUnPreferencesDescription 'Odstráni konfiguračný adresár FuCadUpu $\r$\n\
						$\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						pre všetkých užívateľov (keď máte administrátorské práva).'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUps user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons.$\r$\n\
						Do you agree with this?'
${LangFileString} SecUnProgramFilesDescription "Odinštaluj FuCadUp a všetky jeho súčiastky."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
