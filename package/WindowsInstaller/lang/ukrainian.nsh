/*
FuCadUp Installer Language File
Language: Ukrainian
*/

!insertmacro LANGFILE_EXT "Ukrainian"

${LangFileString} TEXT_INSTALL_CURRENTUSER "(Встановлено для поточного користувача)"

${LangFileString} TEXT_WELCOME "За допомогою цього майстра ви зможете встановити FuCadUp у вашу систему.$\r$\n\
				$\r$\n\
				$_CLICK"

#${LangFileString} TEXT_CONFIGURE_PYTHON "Обробка скриптів Python..."

${LangFileString} TEXT_FINISH_DESKTOP "Створити значок на стільниці"
${LangFileString} TEXT_FINISH_WEBSITE "Відвідати github.com/otherworld-dev/FuCadUp, щоб ознайомитися з новинами, довідковими матеріалами та підказками"

#${LangFileString} FileTypeTitle "Документ FuCadUp"

#${LangFileString} SecAllUsersTitle "Встановити для всіх користувачів?"
${LangFileString} SecFileAssocTitle "Прив’язка файлів"
${LangFileString} SecDesktopTitle "Піктограма стільниці"

${LangFileString} SecCoreDescription "Файли FuCadUp."
#${LangFileString} SecAllUsersDescription "Визначає, чи слід встановити FuCadUp для всіх користувачів, чи лише для поточного користувача."
${LangFileString} SecFileAssocDescription "Файли з суфіксом .FCStd автоматично відкриватимуться за допомогою FuCadUp."
${LangFileString} SecDesktopDescription "Піктограма FuCadUp на стільниці."
#${LangFileString} SecDictionaries "Словники"
#${LangFileString} SecDictionariesDescription "Словники для перевірки правопису, які можна отримати і встановити."

#${LangFileString} PathName 'Розташування файла $\"xxx.exe$\"'
#${LangFileString} InvalidFolder 'У вказаній теці немає файла $\"xxx.exe$\".'

#${LangFileString} DictionariesFailed 'Спроба отримання словника для мови $\"$R3$\" зазнала невдачі.'

#${LangFileString} ConfigInfo "Налаштування FuCadUp може тривати досить довго."

#${LangFileString} RunConfigureFailed "Не вдалося виконати скрипт налаштування"
${LangFileString} InstallRunning "Засіб для встановлення вже працює!"
${LangFileString} AlreadyInstalled "FuCadUp ${APP_SERIES_KEY2} вже встановлено!$\r$\n\
				Чи хочете ви попри ці зауваження встановити FuCadUp на місце наявної версії?"
${LangFileString} NewerInstalled "Ви намагаєтеся встановити версію FuCadUp, яка є застарілою порівняно з вже встановленою.$\r$\n\
				  Якщо ви хочете встановити застарілу версію, вам слід спочатку вилучити вже встановлений FuCadUp $OldVersionNumber."

#${LangFileString} FinishPageMessage "Вітаємо! FuCadUp було успішно встановлено.$\r$\n\
#					$\r$\n\
#					(Перший запуск FuCadUp може тривати декілька секунд.)"
${LangFileString} FinishPageRun "Запустити FuCadUp"

${LangFileString} UnNotInRegistryLabel "Не вдалося знайти записи FuCadUp у регістрі.$\r$\n\
					Записи на стільниці і у меню запуску вилучено не буде."
${LangFileString} UnInstallRunning "Спочатку слід завершити роботу програми FuCadUp!"
${LangFileString} UnNotAdminLabel "Для вилучення FuCadUp вам слід мати привілеї адміністратора!"
${LangFileString} UnReallyRemoveLabel "Ви справді бажаєте повністю вилучити FuCadUp і всі його компоненти?"
${LangFileString} UnFuCadUpPreferencesTitle 'Параметри FuCadUp, встановлені користувачем'

#${LangFileString} SecUnProgDescription "Вилучає xxx."
${LangFileString} SecUnPreferencesDescription 'Вилучає теку з налаштуваннями FuCadUp$\r$\n\
						$\"$AppPre\username\$\r$\n\
						$AppSuff\$\r$\n\
						${APP_DIR_USERDATA}$\")$\r$\n\
						для всіх користувачів.'
${LangFileString} DialogUnPreferences 'You chose to delete the FuCadUps user configuration.$\r$\n\
						This will also delete all installed FuCadUp addons.$\r$\n\
						Do you agree with this?'
${LangFileString} SecUnProgramFilesDescription "Вилучити FuCadUp і всі його компоненти."

${LangFileString} DirNotEmptyWarning "The selected folder '$INSTDIR' is not empty.$\r$\n\
                        The installer will remove all its content before installing. Continue?"
${LangFileString} RMInstDirFailed "Failed to remove '$INSTDIR'.$\r$\n\
                        Make sure you have sufficient permissions and that no files are in use."
