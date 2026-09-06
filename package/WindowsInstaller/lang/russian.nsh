/*
FuCadUp Installer Language File
Language: Russian
*/

!insertmacro LANGFILE_EXT "Russian"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Установлено для текущего пользователя)"

${LangFileString} TEXT_WELCOME "Этот мастер проведет вас через процесс установки $(^NameDA). $\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Компиляция скриптов Python..."

${LangFileString} TEXT_FINISH_DESKTOP "Создать ярлык на рабочем столе"
${LangFileString} TEXT_FINISH_WEBSITE "Перейти на github.com/otherworld-dev/FuCadUp за новостями, поддержкой и советами"

#${LangFileString} FileTypeTitle "FuCadUp-Document"

#${LangFileString} SecAllUsersTitle "Установить для всех пользователей?"
${LangFileString} SecFileAssocTitle "Ассоциации файлов"
${LangFileString} SecDesktopTitle "Значок на рабочем столе"

${LangFileString} SecCoreDescription "Файлы FuCadUp."
#${LangFileString} SecAllUsersDescription "Установить FuCadUp для всех пользователей или только для текущего пользователя."
${LangFileString} SecFileAssocDescription "Файлы с расширением .FCStd будут автоматически открываться в FuCadUp."
${LangFileString} SecDesktopDescription "Значок FuCadUp на рабочем столе."
#${LangFileString} SecDictionaries "Словари"
#${LangFileString} SecDictionariesDescription "Словари для проверки орфографии, которые можно скачать и установить."

#${LangFileString} PathName 'Путь к файлу $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'Файл $\"xxx.exe$\" отсутствует по этому пути.'

#${LangFileString} DictionariesFailed 'Не удалось загрузить словарь для языка $\"$R3$\".'

#${LangFileString} ConfigInfo "Следующая конфигурация FuCadUp займет некоторое время."

#${LangFileString} RunConfigureFailed "Не удалось выполнить сценарий настройки"
${LangFileString} InstallRunning "Установщик уже запущен!"
${LangFileString} AlreadyInstalled "FuCadUp ${APP_SERIES_KEY2} уже установлен!$\r$\n\
				Вы все равно хотите установить FuCadUp поверх существующей версии?"
${LangFileString} NewerInstalled "Вы пытаетесь установить более старую версию FuCadUp, чем уже установленная.$\r$\n\
				  Если вы действительно хотите этого, то сначала необходимо удалить существующий FuCadUp $OldVersionNumber."

#${LangFileString} FinishPageMessage "Поздравляем! FuCadUp был успешно установлен.$\r$\n\
#					$\r$\n\
#					(Первый запуск FuCadUp может занять несколько секунд.)"
${LangFileString} FinishPageRun "Запустить FuCadUp"

${LangFileString} UnNotInRegistryLabel "Не удалось найти FuCadUp в реестре.$\r$\n\
					Ярлыки на рабочем столе и в меню Пуск не будут удалены."
${LangFileString} UnInstallRunning "Вы должны сначала закрыть FuCadUp!"
${LangFileString} UnNotAdminLabel "Необходимо иметь права администратора для удаления FuCadUp!"
${LangFileString} UnReallyRemoveLabel "Вы действительно хотите полностью удалить FuCadUp и все его компоненты?"
${LangFileString} UnFuCadUpPreferencesTitle 'Пользовательские настройки FuCadUp'

#${LangFileString} SecUnProgDescription "Удалить менеджер xxx."
${LangFileString} SecUnPreferencesDescription 'Удалить настройки FuCadUp$\r$\n\
						(каталог $\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						для вас или для всех пользователей (если вы администратор).'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUps user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons.$\r$\n\
						Do you agree with this?'
${LangFileString} SecUnProgramFilesDescription "Удалить FuCadUp и все его компоненты."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
