/***************************************************************************
 *   Copyright (c) 2026 FuCad contributors                                 *
 *                                                                         *
 *   This file is part of FreeCAD.                                         *
 *                                                                         *
 *   FreeCAD is free software: you can redistribute it and/or modify it    *
 *   under the terms of the GNU Lesser General Public License as           *
 *   published by the Free Software Foundation, either version 2.1 of the  *
 *   License, or (at your option) any later version.                       *
 *                                                                         *
 *   FreeCAD is distributed in the hope that it will be useful, but        *
 *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
 *   Lesser General Public License for more details.                       *
 *                                                                         *
 *   You should have received a copy of the GNU Lesser General Public      *
 *   License along with FreeCAD. If not, see                               *
 *   <https://www.gnu.org/licenses/>.                                      *
 *                                                                         *
 ***************************************************************************/


#include <algorithm>

#include <QAction>
#include <QApplication>
#include <QContextMenuEvent>
#include <QCursor>
#include <QDrag>
#include <QDragEnterEvent>
#include <QDragLeaveEvent>
#include <QDragMoveEvent>
#include <QDropEvent>
#include <QEvent>
#include <QFont>
#include <QFontMetrics>
#include <QLabel>
#include <QMenu>
#include <QMimeData>
#include <QMouseEvent>
#include <QPaintEvent>
#include <QPainter>
#include <QPixmap>
#include <QResizeEvent>
#include <QSet>
#include <QSizePolicy>
#include <QStyle>
#include <QTimer>
#include <QToolButton>

#include "RibbonButton.h"
#include "RibbonPanel.h"
#include "RibbonPanelMenu.h"


using namespace Gui::Ribbon;

namespace
{
constexpr int panelSideMargin = 8;
constexpr int panelTopMargin = 2;
constexpr int panelBottomMargin = 1;
constexpr int buttonSpacing = 1;
constexpr int captionPointSizeDelta = 1;
constexpr double minimumCaptionPointSize = 6.0;
constexpr int separatorWidth = 1;
// Only the two border pixels the stylesheet draws: the caption row has to keep
// the height of the label it replaces, or the page outgrows the ribbon.
constexpr int captionButtonBorder = 2;
constexpr int captionButtonMinimumWidth = 56;
constexpr int insertionMarkerWidth = 2;
// Selected on by the stylesheet as [dropTarget="true"] while a drag hovers the caption.
constexpr const char* dropTargetProperty = "dropTarget";
// Read back by tests to put the buttons of a row in order, folded ones included.
constexpr const char* rowIndexProperty = "rowIndex";

/// The commands the entries of \a menu are tagged with, submenus included.
void collectCommands(const QMenu* menu, QSet<QString>& commands)
{
    for (const QAction* action : menu->actions()) {
        const QString command = RibbonPanelMenu::commandOf(action);
        if (!command.isEmpty()) {
            commands.insert(command);
        }
        if (const QMenu* submenu = action->menu()) {
            collectCommands(submenu, commands);
        }
    }
}
}  // namespace


/**
 * The strip the buttons sit on. It has no layout of its own: the panel places
 * the buttons, so the row wants nothing for itself and the panel can be given
 * any width the page has left. It also draws the marker that shows where a
 * dragged entry would land.
 */
class RibbonPanel::Row: public QWidget
{
public:
    explicit Row(QWidget* parent)
        : QWidget(parent)
    {
        setObjectName(QStringLiteral("RibbonPanelButtons"));
        setAttribute(Qt::WA_StyledBackground, true);
    }

    void setMarker(int x)
    {
        if (markerX != x) {
            markerX = x;
            update();
        }
    }

    QSize minimumSizeHint() const override
    {
        return QSize(0, 0);
    }

protected:
    void paintEvent(QPaintEvent* event) override
    {
        QWidget::paintEvent(event);

        if (markerX < 0) {
            return;
        }

        QPainter painter(this);
        painter.fillRect(
            markerX - insertionMarkerWidth / 2,
            0,
            insertionMarkerWidth,
            height(),
            palette().highlight()
        );
    }

private:
    int markerX {-1};
};


RibbonPanel::RibbonPanel(const QString& key, const QString& caption, QWidget* parent)
    : QWidget(parent)
    , key(key)
    , captionText(caption)
    , row(nullptr)
    , captionLabel(nullptr)
    , captionButton(nullptr)
    , separator(nullptr)
    , menu(nullptr)
    , resetAction(nullptr)
    , resetAllAction(nullptr)
{
    setObjectName(QStringLiteral("RibbonPanel"));
    setAttribute(Qt::WA_StyledBackground, true);
    setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Preferred);
    setAcceptDrops(true);

    row = new Row(this);

    captionLabel = new QLabel(captionText, this);
    captionLabel->setObjectName(QStringLiteral("RibbonPanelCaption"));
    captionLabel->setAlignment(Qt::AlignHCenter | Qt::AlignVCenter);
    applyCaptionFont(captionLabel);

    menu = new RibbonPanelMenu(key, this);
    // Named for the page's overflow button, which lists it as a submenu.
    menu->setTitle(captionText);
    connect(menu, &RibbonPanelMenu::entriesChanged, this, [this]() {
        ++menuRevision;
        updateCaption();
    });
    connect(menu, &QMenu::aboutToHide, this, [this]() {
        // Queued: aboutToHide arrives from inside the menu's own hide, which
        // is no place to delete its entries either.
        QTimer::singleShot(0, this, [this]() {
            if (overflowStale) {
                updateOverflowEntries();
            }
        });
    });
    connect(menu, &RibbonPanelMenu::dragStarted, this, [this]() { dragging = true; });
    connect(menu, &RibbonPanelMenu::dragFinished, this, &RibbonPanel::onDragFinished);

    captionButton = new QToolButton(this);
    captionButton->setObjectName(QStringLiteral("RibbonPanelCaptionButton"));
    captionButton->setText(captionText);
    captionButton->setToolButtonStyle(Qt::ToolButtonTextOnly);
    captionButton->setPopupMode(QToolButton::InstantPopup);
    captionButton->setAutoRaise(true);
    // Reached with the arrow keys from the tab strip like every other button of
    // a page, rather than as a tab stop of its own; see RibbonBar::eventFilter.
    captionButton->setFocusPolicy(Qt::NoFocus);
    applyCaptionFont(captionButton);
    captionButton->setMinimumWidth(captionButtonMinimumWidth);
    captionButton->setFixedHeight(captionHeight());
    captionButton->setMenu(menu);
    captionButton->hide();

    const QString dragHint = tr(
        "Drag a button here to keep it in the drop-down only, or drag a drop-down entry "
        "onto the row to show it as a button."
    );
    captionLabel->setToolTip(dragHint);
    captionButton->setToolTip(dragHint);

    // A plain widget rather than a QFrame line: the rule is painted from the
    // stylesheet so that it picks up the border colour of the active theme.
    separator = new QWidget(this);
    separator->setObjectName(QStringLiteral("RibbonPanelSeparator"));
    separator->setAttribute(Qt::WA_StyledBackground, true);

    resetAction = new QAction(tr("Reset this panel"), this);
    resetAction->setObjectName(QStringLiteral("RibbonPanelResetAction"));
    // Until setCustomised() says there is something to go back to.
    resetAction->setEnabled(false);
    connect(resetAction, &QAction::triggered, this, &RibbonPanel::resetRequested);

    resetAllAction = new QAction(tr("Reset every panel"), this);
    resetAllAction->setObjectName(QStringLiteral("RibbonPanelResetAllAction"));
    connect(resetAllAction, &QAction::triggered, this, &RibbonPanel::resetAllRequested);
}

QString RibbonPanel::panelKey() const
{
    return key;
}

void RibbonPanel::addButton(RibbonButton* button)
{
    if (!button) {
        return;
    }

    button->setParent(row);
    button->setProperty(rowIndexProperty, static_cast<int>(buttons.size()));
    button->installEventFilter(this);
    buttons.append(button);
    // The fold is decided when the page first sizes the panel: doing it here
    // would fold against a width that means nothing yet and put entries into
    // a drop-down the caller is still filling.
    updateGeometry();
}

RibbonPanelMenu* RibbonPanel::dropDown() const
{
    return menu;
}

bool RibbonPanel::isEmpty() const
{
    return buttons.isEmpty() && menu->isEmpty();
}

void RibbonPanel::setSeparatorVisible(bool visible)
{
    separator->setVisible(visible);
}

void RibbonPanel::setCustomised(bool customised)
{
    resetAction->setEnabled(customised);
}

void RibbonPanel::setCollapsed(bool collapse)
{
    if (collapsed == collapse) {
        return;
    }

    collapsed = collapse;
    updateOverflow();
}

QStringList RibbonPanel::rowCommands() const
{
    QStringList commands;
    for (const RibbonButton* button : buttons) {
        commands.append(button->command());
    }
    return commands;
}

QList<QToolButton*> RibbonPanel::keyboardButtons() const
{
    QList<QToolButton*> reachable;
    for (RibbonButton* button : buttons) {
        // A disabled button would swallow the keyboard on a command that
        // Return could not run anyway.
        if (button->isEnabled() && button->isVisibleTo(this)) {
            reachable.append(button);
        }
    }
    if (captionButton->isVisibleTo(this)) {
        reachable.append(captionButton);
    }
    return reachable;
}

int RibbonPanel::captionHeight() const
{
    return QFontMetrics(captionLabel->font()).height() + captionButtonBorder;
}

int RibbonPanel::captionWidth() const
{
    // Always the button's width, whether or not it is the one on show: the
    // panel must not ask for a different width when the caption swaps, or the
    // page would lay itself out again in answer to its own layout.
    return std::max(captionButtonMinimumWidth, captionButton->sizeHint().width());
}

int RibbonPanel::widthOf(const RibbonButton* button)
{
    const QSize hint = button->sizeHint().expandedTo(button->minimumSize());
    return hint.boundedTo(button->maximumSize()).width();
}

QSize RibbonPanel::minimumSizeHint() const
{
    int buttonHeight = 0;
    for (const RibbonButton* button : buttons) {
        buttonHeight = std::max(buttonHeight, button->minimumHeight());
    }

    return QSize(
        2 * panelSideMargin + separatorWidth + captionWidth(),
        panelTopMargin + buttonHeight + captionHeight() + panelBottomMargin
    );
}

QSize RibbonPanel::sizeHint() const
{
    int rowWidth = 0;
    for (const RibbonButton* button : buttons) {
        rowWidth += widthOf(button) + buttonSpacing;
    }
    if (rowWidth > 0) {
        rowWidth -= buttonSpacing;
    }

    const QSize minimum = minimumSizeHint();
    return QSize(
        2 * panelSideMargin + separatorWidth + std::max(rowWidth, captionWidth()),
        minimum.height()
    );
}

void RibbonPanel::resizeEvent(QResizeEvent* event)
{
    QWidget::resizeEvent(event);
    layoutChildren();
    updateOverflow();
}

void RibbonPanel::layoutChildren()
{
    const int bodyWidth = std::max(0, width() - 2 * panelSideMargin - separatorWidth);
    const int captionTop = height() - panelBottomMargin - captionHeight();
    const int rowHeight = std::max(0, captionTop - panelTopMargin);

    row->setGeometry(panelSideMargin, panelTopMargin, bodyWidth, rowHeight);
    captionLabel->setGeometry(panelSideMargin, captionTop, bodyWidth, captionHeight());

    const int buttonWidth = std::min(bodyWidth, captionWidth());
    captionButton->setGeometry(
        panelSideMargin + (bodyWidth - buttonWidth) / 2,
        captionTop,
        buttonWidth,
        captionHeight()
    );

    separator->setGeometry(width() - separatorWidth, 0, separatorWidth, height());
}

void RibbonPanel::updateOverflow()
{
    const int available = collapsed ? 0 : row->width();
    int x = 0;
    bool fits = true;
    for (RibbonButton* button : buttons) {
        const int width = widthOf(button);
        if (fits && x + width <= available) {
            button->setGeometry(x, 0, width, button->minimumHeight());
            button->setVisible(true);
            x += width + buttonSpacing;
        }
        else {
            // Strictly in order: a narrower button further along does not jump
            // ahead of a wider one that did not fit, or the row would reorder
            // itself as the window is dragged.
            fits = false;
            button->setVisible(false);
        }
    }

    updateOverflowEntries();
}

void RibbonPanel::updateOverflowEntries()
{
    // The entries are torn down and built again, and an open drop-down may be
    // showing one of them, so the rebuild waits until it has closed.
    if (menu->isVisible()) {
        overflowStale = true;
        return;
    }
    const bool forced = overflowStale;
    overflowStale = false;

    // A resize that folds the same buttons as before, with nothing else added
    // to the drop-down since, has nothing to rebuild.
    QList<RibbonButton*> folded;
    for (RibbonButton* button : buttons) {
        if (!button->isVisibleTo(this)) {
            folded.append(button);
        }
    }
    if (!forced && folded == lastFolded && menuRevision == builtRevision) {
        return;
    }

    for (QObject* entry : overflowEntries) {
        if (auto* submenu = qobject_cast<QMenu*>(entry)) {
            menu->removeAction(submenu->menuAction());
        }
        else if (auto* action = qobject_cast<QAction*>(entry)) {
            menu->removeAction(action);
        }
        delete entry;
    }
    overflowEntries.clear();

    // What the drop-down already lists stays where it is; only a folded button
    // that has no entry of its own gets one.
    QSet<QString> covered;
    collectCommands(menu, covered);

    QAction* first = menu->actions().value(0);
    for (RibbonButton* button : buttons) {
        if (button->isVisibleTo(this) || covered.contains(button->command())) {
            continue;
        }
        covered.insert(button->command());

        QAction* source = button->defaultAction();
        if (!source) {
            continue;
        }

        if (button->menu() && button->popupMode() == QToolButton::MenuButtonPopup) {
            // A split button folds to a submenu of its variants, led by the
            // command a plain click on the button would run.
            RibbonPanelMenu* submenu = menu->insertSubmenu(first, button->text());
            submenu->setIcon(button->icon());
            RibbonPanelMenu::tagCommand(submenu->menuAction(), button->command());
            if (button->splitsExplicitCommands()) {
                QAction* proxy = RibbonPanelMenu::createProxyAction(source, button->text(), submenu);
                RibbonPanelMenu::tagCommand(proxy, button->command());
                submenu->addAction(proxy);
                submenu->addSeparator();
            }
            submenu->addActions(button->menu()->actions());
            overflowEntries.append(submenu);
        }
        else if (button->menu() && button->popupMode() == QToolButton::InstantPopup) {
            // A settings button (Grid, Snap) opens its panel of controls on a
            // click, so its entry opens that panel rather than firing the
            // command; the controls cannot be shared with a second menu.
            QMenu* settings = button->menu();
            auto* proxy = new QAction(button->icon(), button->text(), menu);
            proxy->setToolTip(button->toolTip());
            proxy->setEnabled(source->isEnabled());
            connect(source, &QAction::changed, proxy, [proxy, source]() {
                proxy->setEnabled(source->isEnabled());
            });
            connect(proxy, &QAction::triggered, settings, [settings]() {
                // Queued so that the drop-down has closed before the panel
                // pops up where it was.
                QTimer::singleShot(0, settings, [settings]() { settings->popup(QCursor::pos()); });
            });
            RibbonPanelMenu::tagCommand(proxy, button->command());
            menu->insertAction(first, proxy);
            overflowEntries.append(proxy);
        }
        else {
            QAction* proxy = RibbonPanelMenu::createProxyAction(source, button->text(), menu);
            RibbonPanelMenu::tagCommand(proxy, button->command());
            menu->insertAction(first, proxy);
            overflowEntries.append(proxy);
        }
    }

    if (!overflowEntries.isEmpty() && first) {
        overflowEntries.append(menu->insertSeparator(first));
    }

    lastFolded = folded;
    builtRevision = menuRevision;
}

void RibbonPanel::updateCaption()
{
    const bool hasEntries = !menu->isEmpty();
    captionButton->setVisible(hasEntries);
    captionLabel->setVisible(!hasEntries);
}

void RibbonPanel::applyCaptionFont(QWidget* widget) const
{
    QFont captionFont = widget->font();
    if (captionFont.pointSizeF() <= 0.0) {
        return;
    }

    captionFont.setPointSizeF(
        std::max(minimumCaptionPointSize, captionFont.pointSizeF() - captionPointSizeDelta)
    );
    widget->setFont(captionFont);
}

void RibbonPanel::contextMenuEvent(QContextMenuEvent* event)
{
    // popup() rather than exec(): a reset rebuilds the page, which deletes
    // this panel, and that must not happen inside a loop this method is
    // still waiting on.
    auto* contextMenu = new QMenu(this);
    contextMenu->setAttribute(Qt::WA_DeleteOnClose, true);
    contextMenu->addAction(resetAction);
    contextMenu->addAction(resetAllAction);
    contextMenu->popup(event->globalPos());
    event->accept();
}

// -- dragging a button out of the row ---------------------------------------

RibbonButton* RibbonPanel::buttonAt(const QPoint& position) const
{
    QWidget* child = childAt(position);
    while (child && child != this) {
        if (auto* button = qobject_cast<RibbonButton*>(child)) {
            return button;
        }
        child = child->parentWidget();
    }
    return nullptr;
}

bool RibbonPanel::eventFilter(QObject* watched, QEvent* event)
{
    auto* button = qobject_cast<RibbonButton*>(watched);
    // A disabled button lets its mouse events through to the panel, which
    // handles them in the mouse event handlers below instead.
    if (!button || !button->isEnabled()) {
        return QWidget::eventFilter(watched, event);
    }

    switch (event->type()) {
        case QEvent::MouseButtonPress: {
            auto* mouse = static_cast<QMouseEvent*>(event);
            if (mouse->button() != Qt::LeftButton) {
                return false;
            }
            pressedButton = button;
            pressPosition = mouse->globalPosition().toPoint();
            // An InstantPopup button opens its menu on the press itself, which
            // would end the drag before it started; the press is held back and
            // the menu opened on the release instead.
            pressTaken = button->popupMode() == QToolButton::InstantPopup;
            if (pressTaken) {
                button->setDown(true);
                return true;
            }
            return false;
        }
        case QEvent::MouseMove: {
            auto* mouse = static_cast<QMouseEvent*>(event);
            if (pressedButton != button || !(mouse->buttons() & Qt::LeftButton)) {
                return false;
            }
            if ((mouse->globalPosition().toPoint() - pressPosition).manhattanLength()
                < QApplication::startDragDistance()) {
                return pressTaken;
            }
            pressedButton = nullptr;
            pressTaken = false;
            startDrag(button);
            return true;
        }
        case QEvent::MouseButtonRelease: {
            auto* mouse = static_cast<QMouseEvent*>(event);
            const bool taken = pressTaken && pressedButton == button;
            pressedButton = nullptr;
            pressTaken = false;
            if (!taken) {
                return false;
            }
            button->setDown(false);
            if (button->rect().contains(mouse->position().toPoint())) {
                button->showMenu();
            }
            return true;
        }
        default:
            return QWidget::eventFilter(watched, event);
    }
}

void RibbonPanel::mousePressEvent(QMouseEvent* event)
{
    pressedButton = nullptr;
    pressTaken = false;
    if (event->button() == Qt::LeftButton) {
        if (RibbonButton* button = buttonAt(event->position().toPoint())) {
            pressedButton = button;
            pressPosition = event->globalPosition().toPoint();
            event->accept();
            return;
        }
    }
    QWidget::mousePressEvent(event);
}

void RibbonPanel::mouseMoveEvent(QMouseEvent* event)
{
    if (!pressedButton.isNull() && (event->buttons() & Qt::LeftButton)
        && (event->globalPosition().toPoint() - pressPosition).manhattanLength()
            >= QApplication::startDragDistance()) {
        RibbonButton* button = pressedButton.data();
        pressedButton = nullptr;
        startDrag(button);
        return;
    }
    QWidget::mouseMoveEvent(event);
}

void RibbonPanel::mouseReleaseEvent(QMouseEvent* event)
{
    pressedButton = nullptr;
    pressTaken = false;
    QWidget::mouseReleaseEvent(event);
}

void RibbonPanel::startDrag(RibbonButton* button)
{
    button->setDown(false);

    auto* drag = new QDrag(this);
    drag->setMimeData(RibbonPanelMenu::createMimeData(key, button->command()));
    const QPixmap pixmap = button->grab();
    if (!pixmap.isNull()) {
        drag->setPixmap(pixmap);
        drag->setHotSpot(pixmap.rect().center());
    }

    // The drop is applied only once exec() has returned: the page is rebuilt
    // from it, and a rebuild while the drag still runs would delete the panel
    // and the button under the drag.
    dragging = true;
    // Something other than the drop may still rebuild the page under the
    // drag (a workbench switch from a timer, a context tab being popped),
    // which deletes this panel and, as its child, the drag.
    QPointer<RibbonPanel> self(this);
    drag->exec(Qt::MoveAction);
    if (self) {
        drag->deleteLater();
        onDragFinished();
    }
}

// -- dropping ----------------------------------------------------------------

bool RibbonPanel::acceptsDrop(const QMimeData* data, QString& command) const
{
    QString sourceKey;
    if (!RibbonPanelMenu::readMimeData(data, sourceKey, command)) {
        return false;
    }

    // The drop-down is this panel's own command set, so an entry of another
    // panel has nothing to become here.
    return sourceKey == key;
}

bool RibbonPanel::isOverCaption(const QPoint& position) const
{
    // The whole band under the row counts, so that the caption need not be
    // hit exactly.
    return position.y() >= row->geometry().bottom();
}

int RibbonPanel::insertionIndex(const QPoint& position) const
{
    const int x = position.x() - row->x();
    int index = 0;
    for (const RibbonButton* button : buttons) {
        if (!button->isVisibleTo(this)) {
            break;
        }
        if (x < button->geometry().center().x()) {
            return index;
        }
        ++index;
    }
    // After the last visible button, which is ahead of anything folded away.
    return index;
}

int RibbonPanel::insertionMarkerX(int index) const
{
    if (index < buttons.size() && buttons.at(index)->isVisibleTo(this)) {
        return std::max(1, buttons.at(index)->geometry().left() - 1);
    }
    for (qsizetype i = std::min<qsizetype>(index, buttons.size()) - 1; i >= 0; --i) {
        if (buttons.at(i)->isVisibleTo(this)) {
            return std::min(row->width() - 1, buttons.at(i)->geometry().right() + 1);
        }
    }
    return 1;
}

void RibbonPanel::showDropTarget(const QPoint& position)
{
    if (isOverCaption(position)) {
        row->setMarker(-1);
        setCaptionHighlighted(true);
    }
    else {
        setCaptionHighlighted(false);
        row->setMarker(insertionMarkerX(insertionIndex(position)));
    }
}

void RibbonPanel::clearDropTarget()
{
    row->setMarker(-1);
    setCaptionHighlighted(false);
}

void RibbonPanel::setCaptionHighlighted(bool highlighted)
{
    for (QWidget* caption :
         {static_cast<QWidget*>(captionLabel), static_cast<QWidget*>(captionButton)}) {
        if (caption->property(dropTargetProperty).toBool() == highlighted) {
            continue;
        }
        caption->setProperty(dropTargetProperty, highlighted);
        // A rule that selects on a dynamic property is only re-evaluated once
        // the style is asked to look at the widget again.
        caption->style()->unpolish(caption);
        caption->style()->polish(caption);
        caption->update();
    }
}

void RibbonPanel::dragEnterEvent(QDragEnterEvent* event)
{
    QString command;
    if (!acceptsDrop(event->mimeData(), command)) {
        event->ignore();
        return;
    }

    showDropTarget(event->position().toPoint());
    event->acceptProposedAction();
}

void RibbonPanel::dragMoveEvent(QDragMoveEvent* event)
{
    QString command;
    if (!acceptsDrop(event->mimeData(), command)) {
        event->ignore();
        return;
    }

    showDropTarget(event->position().toPoint());
    event->acceptProposedAction();
}

void RibbonPanel::dragLeaveEvent(QDragLeaveEvent* event)
{
    clearDropTarget();
    event->accept();
}

void RibbonPanel::dropEvent(QDropEvent* event)
{
    clearDropTarget();

    QString command;
    if (!acceptsDrop(event->mimeData(), command)) {
        event->ignore();
        return;
    }

    const QPoint position = event->position().toPoint();
    QStringList commands = rowCommands();
    const qsizetype current = commands.indexOf(command);

    if (isOverCaption(position)) {
        if (current >= 0) {
            commands.removeAt(current);
        }
    }
    else {
        int index = insertionIndex(position);
        if (current >= 0) {
            commands.removeAt(current);
            if (current < index) {
                --index;
            }
        }
        commands.insert(std::min<qsizetype>(index, commands.size()), command);
    }

    event->acceptProposedAction();

    if (commands != rowCommands()) {
        requestRow(commands);
    }
}

void RibbonPanel::requestRow(const QStringList& commands)
{
    if (dragging) {
        pendingRow = commands;
        rowPending = true;
        return;
    }

    Q_EMIT rowChanged(commands);
}

void RibbonPanel::onDragFinished()
{
    dragging = false;
    if (!rowPending) {
        return;
    }

    rowPending = false;
    const QStringList commands = pendingRow;
    pendingRow.clear();
    Q_EMIT rowChanged(commands);
}

#include "moc_RibbonPanel.cpp"
