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


#pragma once

#include <QList>
#include <QPoint>
#include <QPointer>
#include <QSize>
#include <QString>
#include <QStringList>
#include <QWidget>

#include <FCGlobal.h>

class QAction;
class QDragEnterEvent;
class QDragLeaveEvent;
class QDragMoveEvent;
class QDropEvent;
class QLabel;
class QMimeData;
class QMouseEvent;
class QToolButton;

namespace Gui
{
namespace Ribbon
{

class RibbonButton;
class RibbonPanelMenu;

/**
 * A captioned group of ribbon buttons: a horizontal row of buttons with the
 * caption centred underneath and a vertical rule along the right edge that
 * separates the panel from its neighbour.
 *
 * The caption is a plain label while the drop-down under it is empty, and the
 * drop-down button Fusion puts under a panel otherwise. The drop-down lists the
 * full command set of the panel; the row above it carries the frequently used
 * ones, and only as many of those as the width the page gives the panel has
 * room for. The buttons that do not fit fold away into the drop-down rather
 * than pile up, and the panel can shrink to its caption alone.
 *
 * Which commands the row carries is the user's to change: a button dropped on
 * the caption leaves the row for the drop-down, a drop-down entry dropped on
 * the row becomes a button there, and a button dropped elsewhere on the row is
 * moved. The panel only reports the row it was asked for through rowChanged();
 * RibbonManager keeps it and builds the page again from it.
 * @author FuCad contributors
 */
class GuiExport RibbonPanel: public QWidget
{
    Q_OBJECT
    /// Names the panel across pages: "<tab>/<caption>", untranslated.
    Q_PROPERTY(QString panelKey READ panelKey CONSTANT)

public:
    RibbonPanel(const QString& key, const QString& caption, QWidget* parent = nullptr);
    ~RibbonPanel() override = default;

    QString panelKey() const;

    /// Appends \a button to the row; the panel takes ownership.
    void addButton(RibbonButton* button);

    /**
     * The drop-down under the caption, for the caller to fill with the full
     * command set. The caption becomes a drop-down button once it has entries.
     */
    RibbonPanelMenu* dropDown() const;

    /// Whether the panel carries neither a button nor a drop-down entry.
    bool isEmpty() const;

    /// The right-hand rule is dropped on the last panel of a page.
    void setSeparatorVisible(bool visible);

    /**
     * Folds every button into the drop-down, which is how a panel that the
     * page cannot show at all is offered from the page's overflow button.
     */
    void setCollapsed(bool collapsed);

    /// Whether the row is the user's rather than the definition's, which is
    /// what "Reset this panel" has to offer.
    void setCustomised(bool customised);

    /// The commands of the row in order, folded ones included.
    QStringList rowCommands() const;

    /**
     * The buttons the keyboard can reach, in reading order: the visible row
     * buttons, then the caption when it is a drop-down.
     */
    QList<QToolButton*> keyboardButtons() const;

    /// The caption alone, which is what the panel folds down to.
    QSize minimumSizeHint() const override;
    /// Every button of the row, or the caption when that is wider.
    QSize sizeHint() const override;

Q_SIGNALS:
    /// The user asked for the row to carry \a commands, in that order.
    void rowChanged(const QStringList& commands);
    /// The user asked for the row the workspace definition describes.
    void resetRequested();
    /// The user asked for every panel to go back to its definition.
    void resetAllRequested();

protected:
    void resizeEvent(QResizeEvent* event) override;
    void contextMenuEvent(QContextMenuEvent* event) override;
    /// Starts a drag from an enabled row button once the pointer has travelled.
    bool eventFilter(QObject* watched, QEvent* event) override;
    /// A disabled button hands its mouse events up, so a drag from one starts here.
    void mousePressEvent(QMouseEvent* event) override;
    void mouseMoveEvent(QMouseEvent* event) override;
    void mouseReleaseEvent(QMouseEvent* event) override;
    void dragEnterEvent(QDragEnterEvent* event) override;
    void dragMoveEvent(QDragMoveEvent* event) override;
    void dragLeaveEvent(QDragLeaveEvent* event) override;
    void dropEvent(QDropEvent* event) override;

private:
    class Row;

    void layoutChildren();
    /// Shows the leading buttons the row has room for and folds the rest.
    void updateOverflow();
    /// Replaces the folded entries at the top of the drop-down.
    void updateOverflowEntries();
    /// Swaps the caption between label and drop-down button as the drop-down fills.
    void updateCaption();
    void applyCaptionFont(QWidget* widget) const;
    int captionHeight() const;
    int captionWidth() const;
    /// The width of \a button once the row lays it out.
    static int widthOf(const RibbonButton* button);

    RibbonButton* buttonAt(const QPoint& position) const;
    void startDrag(RibbonButton* button);
    /// Whether \a data is an entry of this panel; fills \a command when it is.
    bool acceptsDrop(const QMimeData* data, QString& command) const;
    bool isOverCaption(const QPoint& position) const;
    /// Where in the row a drop at \a position lands, as an index into the row.
    int insertionIndex(const QPoint& position) const;
    /// The x of the insertion marker for that index, in row coordinates.
    int insertionMarkerX(int index) const;
    void showDropTarget(const QPoint& position);
    void clearDropTarget();
    void setCaptionHighlighted(bool highlighted);
    /// Hands the row a drop asked for to rowChanged(), now or once the drag ends.
    void requestRow(const QStringList& commands);
    void onDragFinished();

    QString key;
    QString captionText;
    Row* row;
    QLabel* captionLabel;
    QToolButton* captionButton;
    QWidget* separator;
    RibbonPanelMenu* menu;
    QList<RibbonButton*> buttons;
    /// What updateOverflowEntries() put into the drop-down, to take out again.
    QList<QObject*> overflowEntries;
    QAction* resetAction;
    QAction* resetAllAction;

    QPointer<RibbonButton> pressedButton;
    QPoint pressPosition;
    /// The press was taken from an InstantPopup button so that its menu would
    /// not open before a drag had the chance to start.
    bool pressTaken {false};
    bool dragging {false};
    bool rowPending {false};
    QStringList pendingRow;
    /// The fold changed while the drop-down was open, so its entries are
    /// rebuilt once it has closed rather than under it.
    bool overflowStale {false};
    bool collapsed {false};
    /// What the drop-down's folded entries were last built for, so that a
    /// resize that folds nothing new leaves them alone.
    QList<RibbonButton*> lastFolded;
    int menuRevision {0};
    int builtRevision {-1};

    Q_DISABLE_COPY(RibbonPanel)
};

}  // namespace Ribbon
}  // namespace Gui
