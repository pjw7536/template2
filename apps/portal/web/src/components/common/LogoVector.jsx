import logoPng from "../../assets/images/logo.png"

export function LogoVector(props) {
  const { alt = "Logo", ...imgProps } = props

  return <img src={logoPng} alt={alt} {...imgProps} />
}
