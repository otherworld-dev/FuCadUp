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


#include <array>

#include <QAction>
#include <QColor>
#include <QEvent>
#include <QIcon>
#include <QImage>
#include <QPixmap>
#include <QSize>
#include <QString>
#include <QToolButton>

#include <App/Application.h>
#include <Base/Color.h>
#include <Base/Console.h>
#include <Base/Parameter.h>
#include <Base/ServiceProvider.h>

#include "Application.h"
#include "Command.h"
#include "NavigationBar.h"
#include "StyleParameters/ParameterManager.h"


using namespace Gui;

namespace
{
constexpr int iconExtent = 18;
/// Distance kept between the bar and the bottom edge of the view.
constexpr int bottomInset = 14;

const char* const viewParameters = "User parameter:BaseApp/Preferences/View";

/// A "" entry is a separator. Ordered the way Fusion groups them: getting to the
/// model, then looking at it from somewhere, then how it is drawn.
constexpr std::array<const char*, 11> barCommands = {
    "Std_ViewFitAll",
    "Std_ViewFitSelection",
    "Std_AlignToSelection",
    "",
    "Std_ViewGroup",
    "Std_ViewHome",
    "",
    "Std_DrawStyle",
    "Std_OrthographicCamera",
    "Std_PerspectiveCamera",
    "Std_AxisCross",
};

/// The colour the rest of the application's chrome is accented with.
DEFINE_STYLE_PARAMETER(AccentColor, Base::Color(0.024F, 0.588F, 0.843F));

// FreeCAD draws the geometry of its view icons in a cyan family (#16d0d2,
// #34e0e2, #2bdbdd), a colour nothing else in the window uses. Measured over
// every icon the bar carries, that family covers hues 175 to 186 and then stops:
// nothing at all until 196, and the blues the same icons are drawn with begin at
// 206. The band sits in that gap, wide enough for the cyan with room to spare and
// short of both the accent it moves onto and the blues it must leave alone.
constexpr int cyanHueLow = 170;
constexpr int cyanHueHigh = 190;
/// Below this a pixel is a grey and its hue says nothing worth keeping.
constexpr int minSaturation = 60;

QColor accentColor()
{
    auto* parameters = Base::provideService<StyleParameters::ParameterManager>();

    return parameters->resolve(AccentColor).asValue<QColor>();
}

/// \a image with its cyan geometry moved onto \a accent, everything else as it was.
QImage accented(QImage image, const QColor& accent)
{
    const int accentHue = accent.hue();

    for (int y = 0; y < image.height(); ++y) {
        for (int x = 0; x < image.width(); ++x) {
            const QColor pixel = image.pixelColor(x, y);
            const int hue = pixel.hue();

            if (pixel.alpha() == 0 || pixel.saturation() < minSaturation
                || hue < cyanHueLow || hue > cyanHueHigh) {
                continue;
            }

            // Only the hue: the shading the icon was drawn with is what makes its
            // faces readable, and it lives in the saturation and the value.
            image.setPixelColor(
                x,
                y,
                QColor::fromHsv(accentHue, pixel.saturation(), pixel.value(), pixel.alpha())
            );
        }
    }

    return image;
}

/// \a icon as the bar shows it: at the bar's extent, accented, for \a ratio.
QIcon accentedIcon(const QIcon& icon, const QColor& accent, qreal ratio)
{
    const QPixmap source = icon.pixmap(QSize(iconExtent, iconExtent), ratio);
    if (source.isNull()) {
        return icon;
    }

    QPixmap result = QPixmap::fromImage(
        accented(source.toImage().convertToFormat(QImage::Format_ARGB32), accent)
    );
    result.setDevicePixelRatio(source.devicePixelRatio());

    return QIcon(result);
}
}  // namespace


bool NavigationBar::isEnabled()
{
    return App::GetApplication()
        .GetParameterGroupByPath(viewParameters)
        ->GetBool("UseNavigationBar", true);
}

NavigationBar::NavigationBar(QWidget* view)
    : QToolBar(view)
{
    setObjectName(QStringLiteral("NavigationBar"));
    setAttribute(Qt::WA_StyledBackground, true);
    setMovable(false);
    setFloatable(false);
    setFocusPolicy(Qt::NoFocus);
    setIconSize(QSize(iconExtent, iconExtent));
    setToolButtonStyle(Qt::ToolButtonIconOnly);

    populate();

    view->installEventFilter(this);
    reposition();
    raise();
    show();
}

void NavigationBar::populate()
{
    if (!Application::Instance) {
        return;
    }

    CommandManager& manager = Application::Instance->commandManager();
    for (const char* name : barCommands) {
        if (!*name) {
            addSeparator();
            continue;
        }

        Command* command = manager.getCommandByName(name);
        if (!command) {
            Base::Console().warning("NavigationBar: '%s' is not registered\n", name);
            continue;
        }

        // Through the command rather than through its action, so that a group
        // command brings the drop-down the framework builds for a toolbar.
        command->addTo(this);
    }

    const QColor accent = accentColor();

    for (QToolButton* button : findChildren<QToolButton*>()) {
        button->setFocusPolicy(Qt::NoFocus);

        QAction* action = button->defaultAction();
        if (!action) {
            continue;
        }

        // Onto the button rather than onto the action: the action is the one the
        // command framework hands to the ribbon and the menus too, and recolouring
        // it would carry the accent across the whole application.
        auto accentuate = [button, accent, ratio = devicePixelRatioF()]() {
            button->setIcon(accentedIcon(button->defaultAction()->icon(), accent, ratio));
        };

        accentuate();

        // A group command swaps its icon for the mode last picked, and the button
        // takes that straight from the action. Qt sends the button its event before
        // it emits this, so the accent goes back on over the icon that just arrived.
        connect(action, &QAction::changed, button, accentuate);
    }
}

void NavigationBar::reposition()
{
    QWidget* view = parentWidget();
    if (!view) {
        return;
    }

    // sizeHint rather than the current size: the bar has no layout owner to give
    // it one, so it has to take the width its buttons ask for.
    const QSize wanted = sizeHint();
    resize(wanted);
    move((view->width() - wanted.width()) / 2, view->height() - wanted.height() - bottomInset);
}

bool NavigationBar::eventFilter(QObject* watched, QEvent* event)
{
    if (watched == parentWidget()
        && (event->type() == QEvent::Resize || event->type() == QEvent::Show)) {
        reposition();
        raise();
    }

    return QToolBar::eventFilter(watched, event);
}

#include "moc_NavigationBar.cpp"
